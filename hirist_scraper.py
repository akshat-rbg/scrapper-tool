import asyncio                                                                                                                                                                                                  
import json                                                                                                                                                                                                     
from os import getenv                                                                                                                                                                                           
from typing import Optional                               

import httpx
from fastapi import APIRouter, HTTPException, Query
                                                                                                                                                                                                                
router = APIRouter(prefix="/hirist", tags=["hirist"])                                                                                                                                                           
                                                                                                                                                                                                                
HIRIST_BASE = "https://gladiator.hirist.tech"                                                                                                                                                                   
                                                          
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "                                                                                                                                   
        "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    ),                                                                                                                                                                                                          
    "Accept": "application/json, text/plain, */*",        
    "Referer": "https://www.hirist.tech/",                                                                                                                                                                      
    "sec-ch-ua-platform": '"macOS"',                      
    "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',                                                                                                                            
    "sec-ch-ua-mobile": "?0",                                                                                                                                                                                   
}                                                                                                                                                                                                               
                                                                                                                                                                                                                
                                                                                                                                                                                                                
def _get_session_cookie() -> Optional[str]:
    return getenv("HIRIST_COOKIE")                                                                                                                                                                              
                                                          
                                                                                                                                                                                                                
def _normalize(job: dict) -> dict:
    company = job.get("company") or job.get("companyName") or {}                                                                                                                                                
    if isinstance(company, dict):                         
        company_name = company.get("name") or company.get("companyName")                                                                                                                                        
        company_logo = company.get("logo") or company.get("logoUrl")
    else:                                                                                                                                                                                                       
        company_name = company                            
        company_logo = job.get("logo") or job.get("companyLogo")                                                                                                                                                
                                                                                                                                                                                                                
    return {
        "id": job.get("id") or job.get("_id") or job.get("jobId"),                                                                                                                                              
        "title": job.get("title") or job.get("designation") or job.get("jobTitle"),
        "company": company_name,                                                                                                                                                                                
        "company_logo": company_logo,
        "location": job.get("location") or job.get("city") or job.get("locations"),                                                                                                                             
        "experience": {                                                                                                                                                                                         
            "min": job.get("minExp") or job.get("minexp"),
            "max": job.get("maxExp") or job.get("maxexp"),                                                                                                                                                      
        },                                                
        "salary": {                                                                                                                                                                                             
            "min": job.get("minSal") or job.get("minsal"),
            "max": job.get("maxSal") or job.get("maxsal"),                                                                                                                                                      
            "currency": job.get("currency"),
        },                                                                                                                                                                                                      
        "skills": job.get("skills") or job.get("keySkills") or [],
        "description": job.get("description") or job.get("jobDescription"),                                                                                                                                     
        "posted_at": job.get("postedOn") or job.get("createdOn") or job.get("postedDate"),
        "url": job.get("url") or job.get("jobUrl"),                                                                                                                                                             
        "role_type": job.get("roleType") or job.get("employmentType"),                                                                                                                                          
    }                                                                                                                                                                                                           
                                                                                                                                                                                                                
                                                          
async def _fetch_page(                                                                                                                                                                                          
    client: httpx.AsyncClient,                            
    page: int,
    min_exp: int,
    max_exp: int,
    extra: dict,                                                                                                                                                                                                
) -> dict:
    ref_pool = json.dumps({"minexp": str(min_exp), "maxexp": str(max_exp)})                                                                                                                                     
    params = {                                                                                                                                                                                                  
        "minexp": min_exp,                                                                                                                                                                                      
        "maxexp": max_exp,                                                                                                                                                                                      
        "page": page,                                                                                                                                                                                           
        "query": 1,                                       
        "refPool": ref_pool,
        **extra,
    }                                                                                                                                                                                                           
    resp = await client.get(f"{HIRIST_BASE}/job/jobfeed", params=params)
    if resp.status_code in (401, 403):                                                                                                                                                                          
        raise HTTPException(                                                                                                                                                                                    
            status_code=401,
            detail="Hirist auth expired — refresh HIRIST_COOKIE env var",                                                                                                                                       
        )                                                                                                                                                                                                       
    if resp.status_code != 200:
        raise HTTPException(                                                                                                                                                                                    
            status_code=502, detail=f"Hirist returned {resp.status_code}"
        )                                                                                                                                                                                                       
    return resp.json()
                                                                                                                                                                                                                
                                                                                                                                                                                                                
@router.get("/jobs")
async def get_jobs(                                                                                                                                                                                             
    min_exp: int = Query(0, ge=0, le=30, description="Minimum years of experience"),
    max_exp: int = Query(30, ge=0, le=30, description="Maximum years of experience"),                                                                                                                           
    pages: int = Query(1, ge=1, le=20, description="Number of pages (0-indexed internally)"),
    raw: bool = Query(False, description="Return raw API response without normalization"),                                                                                                                      
):                                                                                                                                                                                                              
    if min_exp > max_exp:                                                                                                                                                                                       
        raise HTTPException(status_code=400, detail="min_exp must be <= max_exp")                                                                                                                               
                                                                                                                                                                                                                
    cookie = _get_session_cookie()
    if not cookie:                                                                                                                                                                                              
        raise HTTPException(                              
            status_code=500,
            detail="HIRIST_COOKIE env var not set. Copy from your logged-in browser session.",                                                                                                                  
        )                                                                                                                                                                                                       
                                                                                                                                                                                                                
    headers = {**DEFAULT_HEADERS, "Cookie": cookie}                                                                                                                                                             
                                                          
    async with httpx.AsyncClient(                                                                                                                                                                               
        headers=headers, timeout=20.0, follow_redirects=True
    ) as client:                                                                                                                                                                                                
        results = await asyncio.gather(                   
            *(
                _fetch_page(client, p, min_exp, max_exp, {})                                                                                                                                                    
                for p in range(0, pages)
            ),                                                                                                                                                                                                  
            return_exceptions=True,                       
        )                                                                                                                                                                                                       
 
    all_jobs, errors = [], []                                                                                                                                                                                   
    for i, r in enumerate(results):                       
        if isinstance(r, Exception):
            errors.append({"page": i, "error": str(r)})                                                                                                                                                         
            continue
        page_jobs = (                                                                                                                                                                                           
            r.get("jobs")                                 
            or r.get("data")                                                                                                                                                                                    
            or r.get("results")
            or r.get("jobFeed")                                                                                                                                                                                 
            or r.get("feed")                              
            or (r if isinstance(r, list) else [])
        )                                                                                                                                                                                                       
        all_jobs.extend(page_jobs)
                                                                                                                                                                                                                
    return {                                              
        "count": len(all_jobs),
        "min_exp": min_exp,                                                                                                                                                                                     
        "max_exp": max_exp,
        "pages": pages,                                                                                                                                                                                         
        "errors": errors,                                 
        "jobs": all_jobs if raw else [_normalize(j) for j in all_jobs],
    }