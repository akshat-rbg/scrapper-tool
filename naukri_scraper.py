import asyncio
import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from browser import get_browser, UA

router = APIRouter(prefix="/naukri", tags=["naukri"])


def _slugify(text: str) -> str:
  text = text.strip().lower()
  text = re.sub(r"[,\s]+", "-", text)
  text = re.sub(r"[^a-z0-9-]", "", text)
  return text.strip("-")


def _build_url(
  keyword: str, location: str, page: int, experience: Optional[int]
) -> str:
  kw_slug = _slugify(keyword)
  loc_slug = _slugify(location)
  base = f"https://www.naukri.com/{kw_slug}-jobs-in-{loc_slug}"
  if page > 1:
      base = f"{base}-{page}"
  url = f"{base}?k={keyword}&l={location}&sort=f"
  if experience is not None:
      url += f"&experience={experience}"
  return url


_EXP_RE = re.compile(r"(\d+)\s*(?:-\s*(\d+))?\s*Yrs?", re.IGNORECASE)


def _parse_exp(exp_str: str) -> tuple[Optional[int], Optional[int]]:
  if not exp_str:
      return (None, None)
  m = _EXP_RE.search(exp_str)
  if not m:
      return (None, None)
  lo = int(m.group(1))
  hi = int(m.group(2)) if m.group(2) else lo
  return (lo, hi)


def _matches_experience(job_exp: str, requested: Optional[int]) -> bool:
  if requested is None:
      return True
  lo, hi = _parse_exp(job_exp)
  if lo is None:
      return True
  return lo <= requested <= hi


async def _scrape_page(url: str) -> list[dict]:
  browser = get_browser()
  ctx = await browser.new_context(
      viewport={"width": 1366, "height": 768}, user_agent=UA
  )
  page = await ctx.new_page()
  try:
      await page.goto(url, wait_until="domcontentloaded", timeout=30000)
      try:
          await page.wait_for_selector(".srp-jobtuple-wrapper", timeout=15000)
      except Exception:
          html = await page.content()
          if "Access Denied" in html:
              raise HTTPException(
                  status_code=502, detail="Naukri blocked the request"
              )
          return []

      jobs = await page.evaluate("""                                                                                                                                                                             
      () => Array.from(document.querySelectorAll('.srp-jobtuple-wrapper')).map(card => {
          const q = (sel) => card.querySelector(sel);                                                                                                                                                            
          const text = (sel) => { const el = q(sel); return el ? el.innerText.trim() : ''; };
          const attr = (sel, a) => { const el = q(sel); return el ? el.getAttribute(a) : ''; };                                                                                                                  
          const titleEl = q('a.title');                                                                                                                                                                          
          return {                                                                                                                                                                                               
              title: titleEl ? titleEl.innerText.trim() : '',                                                                                                                                                    
              url: titleEl ? titleEl.getAttribute('href') : '',                                                                                                                                                  
              company: text('a.comp-name'),                                                                                                                                                                      
              company_url: attr('a.comp-name', 'href'),
              experience: text('.expwdth'),                                                                                                                                                                      
              location: text('.locWdth'),               
              salary: text('.sal-wrap span') || text('.sal'),                                                                                                                                                    
              description: text('.job-desc'),           
              skills: Array.from(card.querySelectorAll('.tags-gt li')).map(li => li.innerText.trim()),                                                                                                           
              posted: text('.job-post-day'),                                                                                                                                                                     
              rating: text('.rating .main-2'),                                                                                                                                                                   
              reviews: text('.review'),                                                                                                                                                                          
          };                                                                                                                                                                                                     
      })                                                                                                                                                                                                         
      """)
      return jobs
  finally:
      await ctx.close()


async def _fetch_applicants(job_url: str) -> dict:
  if not job_url:
      return {}
  browser = get_browser()
  ctx = await browser.new_context(
      viewport={"width": 1366, "height": 768}, user_agent=UA
  )
  page = await ctx.new_page()
  try:
      await page.goto(job_url, wait_until="domcontentloaded", timeout=25000)
      await page.wait_for_timeout(1500)
      data = await page.evaluate("""
      () => {                                                                                                                                                                                                    
          const result = { applicants: '', openings: '', posted_on: '', views: '' };
          const all = document.querySelectorAll('span, div, label');                                                                                                                                             
          for (const el of all) {
              const t = (el.innerText || '').trim();                                                                                                                                                             
              if (!t || t.length > 80) continue;                                                                                                                                                                 
              const lower = t.toLowerCase();
              if (!result.applicants && lower.includes('applicant')) result.applicants = t;                                                                                                                      
              else if (!result.openings && lower.includes('opening'))  result.openings  = t;
              else if (!result.posted_on && lower.startsWith('posted')) result.posted_on = t;                                                                                                                    
              else if (!result.views && lower.includes('view')) result.views = t;
              if (result.applicants && result.openings && result.posted_on) break;                                                                                                                               
          }                                                                                                                                                                                                      
          return result;                                                                                                                                                                                         
      }                                                                                                                                                                                                          
      """)
      return data
  except Exception as e:
      return {"error": str(e)[:120]}
  finally:
      await ctx.close()


async def _enrich_with_applicants(jobs: list[dict], concurrency: int = 5) -> list[dict]:
  sem = asyncio.Semaphore(concurrency)

  async def _one(j):
      async with sem:
          extra = await _fetch_applicants(j.get("url", ""))
          j.update(extra)
          return j

  return await asyncio.gather(*(_one(j) for j in jobs))


@router.get("/jobs")
async def get_jobs(
  keywords: str = Query(
      ..., description="One stack ('react node') OR comma-separated for OR"
  ),
  location: str = Query(..., description="City, e.g. 'bangalore'"),
  experience: Optional[int] = Query(None, ge=0, le=30),
  pages: int = Query(1, ge=1, le=10),
  with_applicants: bool = Query(False),
  strict_experience: bool = Query(True),
):
  if get_browser() is None:
      raise HTTPException(status_code=503, detail="Browser not initialized")

  keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]

  urls = [
      _build_url(kw, location, p, experience)
      for kw in keyword_list
      for p in range(1, pages + 1)
  ]
  results = await asyncio.gather(
      *(_scrape_page(u) for u in urls), return_exceptions=True
  )

  all_jobs, errors = [], []
  for i, r in enumerate(results):
      if isinstance(r, Exception):
          errors.append({"url_index": i, "error": str(r)})
      else:
          all_jobs.extend(r)

  seen, unique = set(), []
  for j in all_jobs:
      u = j.get("url", "")
      if u and u not in seen:
          seen.add(u)
          unique.append(j)
  all_jobs = unique

  if strict_experience and experience is not None:
      all_jobs = [
          j
          for j in all_jobs
          if _matches_experience(j.get("experience", ""), experience)
      ]

  if with_applicants and all_jobs:
      all_jobs = await _enrich_with_applicants(all_jobs)

  return {
      "count": len(all_jobs),
      "keywords": keyword_list,
      "location": location,
      "experience": experience,
      "strict_experience": strict_experience,
      "pages_per_keyword": pages,
      "with_applicants": with_applicants,
      "errors": errors,
      "jobs": all_jobs,
  }
