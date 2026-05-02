import asyncio                                                                                                                                                                                                     
import random
import re                                                                                                                                                                                                          
from typing import Literal, Optional                      
from urllib.parse import quote_plus

from fastapi import APIRouter, HTTPException, Query                                                                                                                                                                
 
from browser import get_browser, UA                                                                                                                                                                                
                                                        
router = APIRouter(prefix="/linkedin", tags=["linkedin"])                                                                                                                                                          
                                                        
                                                                                                                                                                                                                 
# Years → LinkedIn seniority filter (f_E).
# 1=Internship, 2=Entry, 3=Associate, 4=Mid-Senior, 5=Director, 6=Executive                                                                                                                                        
def _exp_to_f_e(years: Optional[int]) -> Optional[str]:                                                                                                                                                            
  if years is None:                                                                                                                                                                                              
      return None                                                                                                                                                                                                
  if years <= 0:                                                                                                                                                                                                 
      return "1,2"                                      
  if years <= 2:
      return "2,3"                                                                                                                                                                                               
  if years <= 5:
      return "3,4"                                                                                                                                                                                               
  if years <= 9:                                        
      return "4"
  if years <= 14:
      return "4,5"                                                                                                                                                                                               
  return "5,6"
                                                                                                                                                                                                                 
                                                                                                                                                                                                                 
# Recency filter (f_TPR) — seconds expressed as 'r<seconds>'.
_TPR_MAP = {                                                                                                                                                                                                       
  "day": "r86400",                                      
  "week": "r604800",                                                                                                                                                                                             
  "month": "r2592000",
}                                                                                                                                                                                                                  
                                                        

def _build_url(
  keyword: str,
  location: str,
  start: int,
  f_e: Optional[str],
  tpr: Optional[str],                                                                                                                                                                                            
) -> str:
  base = (                                                                                                                                                                                                       
      "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
      f"?keywords={quote_plus(keyword)}"                                                                                                                                                                         
      f"&location={quote_plus(location)}"
      f"&start={start}"                                                                                                                                                                                          
      "&sortBy=DD"                                      
  )                                                                                                                                                                                                              
  if f_e:
      base += f"&f_E={f_e}"                                                                                                                                                                                      
  if tpr:                                               
      base += f"&f_TPR={tpr}"
  return base

                                                                                                                                                                                                                 
_SENIORITY_TO_RANGE = {
  "internship": (0, 1),                                                                                                                                                                                          
  "entry level": (0, 2),                                                                                                                                                                                         
  "associate": (2, 5),
  "mid-senior level": (5, 9),                                                                                                                                                                                    
  "director": (9, 15),                                                                                                                                                                                           
  "executive": (15, 30),
}                                                                                                                                                                                                                  
                                                        
                                                                                                                                                                                                                 
def _matches_experience(seniority: str, requested: Optional[int]) -> bool:
  if requested is None:                                                                                                                                                                                          
      return True                                       
  if not seniority:
      return True
  rng = _SENIORITY_TO_RANGE.get(seniority.strip().lower())                                                                                                                                                       
  if not rng:
      return True                                                                                                                                                                                                
  lo, hi = rng                                                                                                                                                                                                   
  return lo <= requested <= hi
                                                                                                                                                                                                                 
                                                        
async def _scrape_page(url: str) -> list[dict]:
  browser = get_browser()
  ctx = await browser.new_context(                                                                                                                                                                               
      viewport={"width": 1366, "height": 768}, user_agent=UA
  )                                                                                                                                                                                                              
  page = await ctx.new_page()                           
  try:                                                                                                                                                                                                           
      resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
      if resp and resp.status == 429:
          raise HTTPException(status_code=429, detail="LinkedIn rate-limited")                                                                                                                                   
      if resp and resp.status >= 500:                                                                                                                                                                            
          return []                                                                                                                                                                                              
                                                                                                                                                                                                                 
      try:                                              
          await page.wait_for_selector(
              "div.base-card, li.jobs-search__results-list-item", timeout=10000                                                                                                                                  
          )                                                                                                                                                                                                      
      except Exception:                                                                                                                                                                                          
          html = await page.content()                                                                                                                                                                            
          if "challenge" in html.lower() or "authwall" in html.lower():
              raise HTTPException(                                                                                                                                                                               
                  status_code=502, detail="LinkedIn blocked the request"
              )                                                                                                                                                                                                  
          return []                                     
                                                                                                                                                                                                                 
      jobs = await page.evaluate("""                    
      () => {
          const cards = document.querySelectorAll('div.base-card, li.jobs-search__results-list-item');
          return Array.from(cards).map(card => {                                                                                                                                                                 
              const q = (sel) => card.querySelector(sel);
              const text = (sel) => { const el = q(sel); return el ? el.innerText.trim() : ''; };                                                                                                                
              const attr = (sel, a) => { const el = q(sel); return el ? el.getAttribute(a) : ''; };                                                                                                              
              const linkEl = q('a.base-card__full-link') || q('a[href*="/jobs/view/"]');                                                                                                                         
              let url = linkEl ? linkEl.getAttribute('href') : '';                                                                                                                                               
              if (url) url = url.split('?')[0];                                                                                                                                                                  
              const idMatch = (url || '').match(/\\/jobs\\/view\\/(\\d+)/) ||                                                                                                                                    
                              ((card.getAttribute('data-entity-urn') || '').match(/(\\d+)/));                                                                                                                    
              return {                                                                                                                                                                                           
                  job_id: idMatch ? idMatch[1] : '',                                                                                                                                                             
                  title: text('h3.base-search-card__title') || text('.base-search-card__title'),                                                                                                                 
                  url: url,                                                                                                                                                                                      
                  company: text('h4.base-search-card__subtitle a') || text('h4.base-search-card__subtitle'),
                  company_url: attr('h4.base-search-card__subtitle a', 'href'),                                                                                                                                  
                  location: text('.job-search-card__location'),                                                                                                                                                  
                  posted: text('time.job-search-card__listdate--new') || text('time.job-search-card__listdate') || text('time'),                                                                                 
                  posted_at: attr('time', 'datetime'),                                                                                                                                                           
                  salary: text('.job-search-card__salary-info'),                                                                                                                                                 
                  benefits: text('.result-benefits__text'),                                                                                                                                                      
              };                                        
          }).filter(j => j.title && j.url);                                                                                                                                                                      
      }                                                 
      """)                                                                                                                                                                                                       
      return jobs                                       
  finally:
      await ctx.close()

                                                                                                                                                                                                                 
async def _fetch_details(job_url: str) -> dict:
  if not job_url:                                                                                                                                                                                                
      return {}                                         
  m = re.search(r"/jobs/view/(\d+)", job_url)
  detail_url = (                                                                                                                                                                                                 
      f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{m.group(1)}"
      if m                                                                                                                                                                                                       
      else job_url                                                                                                                                                                                               
  )                                                                                                                                                                                                              
                                                                                                                                                                                                                 
  browser = get_browser()                               
  ctx = await browser.new_context(
      viewport={"width": 1366, "height": 768}, user_agent=UA
  )
  page = await ctx.new_page()
  try:                                                                                                                                                                                                           
      await page.goto(detail_url, wait_until="domcontentloaded", timeout=25000)
      await page.wait_for_timeout(800)                                                                                                                                                                           
      data = await page.evaluate("""                                                                                                                                                                             
      () => {
          const text = (sel) => { const el = document.querySelector(sel); return el ? el.innerText.trim() : ''; };                                                                                               
          const result = {                                                                                                                                                                                       
              description: text('.show-more-less-html__markup') || text('.description__text'),
              applicants: text('.num-applicants__caption') || text('figcaption.num-applicants__caption'),                                                                                                        
              seniority: '',                                                                                                                                                                                     
              employment_type: '',                                                                                                                                                                               
              job_function: '',                                                                                                                                                                                  
              industries: '',                           
          };                                                                                                                                                                                                     
          const items = document.querySelectorAll('li.description__job-criteria-item, .description__job-criteria-item');
          items.forEach(item => {                                                                                                                                                                                
              const h = (item.querySelector('.description__job-criteria-subheader, h3') || {}).innerText || '';
              const v = (item.querySelector('.description__job-criteria-text, span') || {}).innerText || '';                                                                                                     
              const key = h.trim().toLowerCase();                                                                                                                                                                
              const val = v.trim();                                                                                                                                                                              
              if (key.includes('seniority')) result.seniority = val;                                                                                                                                             
              else if (key.includes('employment')) result.employment_type = val;                                                                                                                                 
              else if (key.includes('function')) result.job_function = val;
              else if (key.includes('industries')) result.industries = val;                                                                                                                                      
          });                                           
          return result;                                                                                                                                                                                         
      }                                                 
      """)
      return data
  except Exception as e:
      return {"error": str(e)[:120]}
  finally:                                                                                                                                                                                                       
      await ctx.close()
                                                                                                                                                                                                                 
                                                                                                                                                                                                                 
async def _enrich_with_details(jobs: list[dict], concurrency: int = 2) -> list[dict]:
  sem = asyncio.Semaphore(concurrency)                                                                                                                                                                           
                                                        
  async def _one(j):
      async with sem:
          await asyncio.sleep(random.uniform(0.4, 1.2))  # dodge rate-limit
          extra = await _fetch_details(j.get("url", ""))                                                                                                                                                         
          j.update(extra)
          return j                                                                                                                                                                                               
                                                        
  return await asyncio.gather(*(_one(j) for j in jobs))                                                                                                                                                          
 
                                                                                                                                                                                                                 
@router.get("/jobs")                                      
async def get_jobs(
  keywords: str = Query(
      ..., description="One stack ('react node') OR comma-separated for OR ('react,angular,node,mern')"
  ),                                                                                                                                                                                                             
  location: str = Query(..., description="City/region, e.g. 'Bangalore' or 'India'"),
  experience: Optional[int] = Query(                                                                                                                                                                             
      None, ge=0, le=30, description="Years; mapped to LinkedIn seniority filter"
  ),                                                                                                                                                                                                             
  pages: int = Query(1, ge=1, le=10, description="Pages per keyword (~25 jobs each)"),
  posted_within: Literal["day", "week", "month"] = Query(                                                                                                                                                        
      "week", description="Recency filter: day | week | month"                                                                                                                                                   
  ),                                                                                                                                                                                                             
  with_details: bool = Query(                                                                                                                                                                                    
      False,                                            
      description="Visit each JD page for description, applicants, seniority (slow)",
  ),                                                                                                                                                                                                             
  strict_experience: bool = Query(
      True,                                                                                                                                                                                                      
      description="Drop jobs whose seniority doesn't match requested years (needs with_details=true)",
  ),                                                                                                                                                                                                             
):
  if get_browser() is None:                                                                                                                                                                                      
      raise HTTPException(status_code=503, detail="Browser not initialized")

  keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]                                                                                                                                           
  f_e = _exp_to_f_e(experience)
  tpr = _TPR_MAP.get(posted_within)                                                                                                                                                                              
                                                        
  urls = [
      _build_url(kw, location, (p - 1) * 25, f_e, tpr)
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
      key = j.get("job_id") or j.get("url", "")                                                                                                                                                                  
      if key and key not in seen:                       
          seen.add(key)
          unique.append(j)
  all_jobs = unique                                                                                                                                                                                              
 
  if with_details and all_jobs:                                                                                                                                                                                  
      all_jobs = await _enrich_with_details(all_jobs)   

  if strict_experience and experience is not None and with_details:                                                                                                                                              
      all_jobs = [
          j for j in all_jobs if _matches_experience(j.get("seniority", ""), experience)                                                                                                                         
      ]                                                 
                                                                                                                                                                                                                 
  return {
      "count": len(all_jobs),                                                                                                                                                                                    
      "keywords": keyword_list,                         
      "location": location,
      "experience": experience,
      "f_E": f_e,
      "posted_within": posted_within,
      "strict_experience": strict_experience,                                                                                                                                                                    
      "pages_per_keyword": pages,
      "with_details": with_details,                                                                                                                                                                              
      "errors": errors,                                 
      "jobs": all_jobs,
  }    