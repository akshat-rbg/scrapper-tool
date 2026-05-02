import asyncio                                                                                                                                                                                                  
from os import getenv                                     
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/cutshort", tags=["cutshort"])                                                                                                                                                       
 
CUTSHORT_BASE = "https://cutshort.io"                                                                                                                                                                           
                                                          
                                                                                                                                                                                                                
def _get_session_cookie() -> Optional[str]:
    return getenv("CUTSHORT_COOKIE")                                                                                                                                                                            
                                                          
                                                                                                                                                                                                                
# Cutshort joins multi-value filters with '-' instead of ','.
def _csv_to_dash(s: Optional[str]) -> Optional[str]:                                                                                                                                                            
    if not s:                                             
        return None
    parts = [x.strip() for x in s.split(",") if x.strip()]
    return "-".join(parts) if parts else None                                                                                                                                                                   
 
                                                                                                                                                                                                                
def _normalize(job: dict) -> dict:                        
    cd = job.get("companyDetails") or {}
    exp = job.get("expRange") or {}                                                                                                                                                                             
    sal = job.get("salaryRange") or {}
    ai = job.get("aiGeneratedData") or {}                                                                                                                                                                       
    creator = job.get("createdBy") or {}                                                                                                                                                                        
 
    exp_min = exp.get("min")                                                                                                                                                                                    
    exp_max = exp.get("max")                              
    exp_label = (                                                                                                                                                                                               
        f"{exp_min}-{exp_max} yrs"                        
        if exp_min is not None and exp_max is not None                                                                                                                                                          
        else None
    )                                                                                                                                                                                                           
                                                          
    return {                                                                                                                                                                                                    
        "id": job.get("_id"),                             
        "short_id": job.get("short_id"),
        "title": job.get("headline"),
        "ai_role": ai.get("jobHeadline"),                                                                                                                                                                       
        "ai_summary": ai.get("rolesAndResponsibilities"),
        "category": ai.get("classifier"),                                                                                                                                                                       
        "company": job.get("company"),                                                                                                                                                                          
        "company_logo": cd.get("logo"),                                                                                                                                                                         
        "company_size": cd.get("size"),                                                                                                                                                                         
        "company_type": cd.get("type"),                   
        "company_stage": cd.get("stage"),                                                                                                                                                                       
        "company_website": (cd.get("links") or {}).get("website"),
        "company_followers": cd.get("followersCount"),                                                                                                                                                          
        "experience": {"min": exp_min, "max": exp_max, "label": exp_label},                                                                                                                                     
        "salary": {                                                                                                                                                                                             
            "label": job.get("salaryRangeText"),                                                                                                                                                                
            "min": sal.get("min"),                        
            "max": sal.get("max"),                                                                                                                                                                              
            "currency": sal.get("currency"),              
        },                                                                                                                                                                                                      
        "location": job.get("locationsText"),
        "locations": job.get("locations") or [],                                                                                                                                                                
        "remote_type": job.get("remoteType"),                                                                                                                                                                   
        "remote": job.get("remoteRole"),
        "role_types": job.get("roleTypes") or [],                                                                                                                                                               
        "skills": job.get("allSkills") or [],                                                                                                                                                                   
        "skills_with_codes": job.get("allSkillsObj") or {},
        "description": job.get("comment"),                                                                                                                                                                      
        "description_html": job.get("richComment"),       
        "saves_count": len(job.get("savedJobsBy") or []),                                                                                                                                                       
        "posted_by": creator.get("name"),                 
        "posted_at": job.get("creationDate"),                                                                                                                                                                   
        "updated_at": job.get("lastUpdateDate"),          
        "is_expired": job.get("isExpired", False),                                                                                                                                                              
        "is_saved": job.get("isJobSaved", False),         
        "url": job.get("publicUrl") or job.get("public_url"),                                                                                                                                                   
        "apply_url": job.get("authApplyUrl"),             
        "relevance_score": job.get("finalrelevancescore") or job.get("score"),                                                                                                                                  
    }                                                                                                                                                                                                           
                                                                                                                                                                                                                
                                                                                                                                                                                                                
def _build_filter_params(                                 
    skills: Optional[str],
    locations: Optional[str],
    role_type: Optional[str],                                                                                                                                                                                   
    remote_type: Optional[str],
    min_salary: Optional[int],                                                                                                                                                                                  
    max_salary: Optional[int],                            
    currency: Optional[str],
    min_exp: Optional[float],                                                                                                                                                                                   
    max_exp: Optional[float],
    hiring_activity: Optional[str],                                                                                                                                                                             
) -> dict:                                                
    params: dict = {}
    if skills:
        params["skills"] = _csv_to_dash(skills)                                                                                                                                                                 
    if locations:
        params["locations"] = _csv_to_dash(locations)                                                                                                                                                           
    if role_type:                                         
        params["roletype"] = role_type
    if remote_type:                                                                                                                                                                                             
        params["remoteType"] = _csv_to_dash(remote_type)
    if min_salary is not None:                                                                                                                                                                                  
        params["minsal"] = min_salary                     
    if max_salary is not None:                                                                                                                                                                                  
        params["maxsal"] = max_salary
    if currency:                                                                                                                                                                                                
        params["salaryCurrency"] = currency               
    if min_exp is not None:
        params["minexp"] = min_exp
    if max_exp is not None:                                                                                                                                                                                     
        params["maxexp"] = max_exp
    if hiring_activity:                                                                                                                                                                                         
        params["hiringActivityOnJob"] = hiring_activity   
    return params                                                                                                                                                                                               
 
                                                                                                                                                                                                                
async def _fetch_page(                                    
    client: httpx.AsyncClient, user_id: str, page: int, extra: dict
) -> dict:
    resp = await client.get(
        f"{CUTSHORT_BASE}/findjobs/q",                                                                                                                                                                          
        params={"page": page, "matchesfor": user_id, **extra},
    )                                                                                                                                                                                                           
    if resp.status_code in (401, 403):                    
        raise HTTPException(                                                                                                                                                                                    
            status_code=401,                              
            detail="Cutshort auth expired — refresh CUTSHORT_COOKIE env var",
        )                                                                                                                                                                                                       
    if resp.status_code != 200:
        raise HTTPException(                                                                                                                                                                                    
            status_code=502, detail=f"Cutshort returned {resp.status_code}"
        )                                                                                                                                                                                                       
    return resp.json()
                                                                                                                                                                                                                
                                                          
@router.get("/jobs")
async def get_jobs(
    user_id: str = Query(                                                                                                                                                                                       
        ..., description="Your Cutshort user ID (the 'matchesfor' value)"
    ),                                                                                                                                                                                                          
    pages: int = Query(1, ge=1, le=20),                   
    skills: Optional[str] = Query(                                                                                                                                                                              
        None,                                             
        description="Comma-separated Cutshort skill CODES, e.g. '00368,00306'",
    ),                                                                                                                                                                                                          
    locations: Optional[str] = Query(
        None,                                                                                                                                                                                                   
        description="Comma-separated, e.g. 'Bengaluru (Bangalore),Hyderabad'",
    ),                                                                                                                                                                                                          
    role_type: Optional[str] = Query(
        None, description="full_time | part_time | contract | internship"                                                                                                                                       
    ),                                                                                                                                                                                                          
    remote_type: Optional[str] = Query(
        None,                                                                                                                                                                                                   
        description="Comma-separated: remote_only,remote_okay,remote_not_okay",
    ),                                                                                                                                                                                                          
    min_salary: Optional[int] = Query(None, ge=0),
    max_salary: Optional[int] = Query(None, ge=0),                                                                                                                                                              
    currency: Optional[str] = Query(None, description="INR, USD, etc."),
    min_exp: Optional[float] = Query(None, ge=0, le=30),                                                                                                                                                        
    max_exp: Optional[float] = Query(None, ge=0, le=30),
    hiring_activity: Optional[str] = Query(                                                                                                                                                                     
        None, description="e.g., '2-days', '7-days', '30-days'"
    ),                                                                                                                                                                                                          
    raw: bool = Query(False, description="Return raw API response without normalization"),
):                                                                                                                                                                                                              
    cookie = _get_session_cookie()                        
    if not cookie:                                                                                                                                                                                              
        raise HTTPException(
            status_code=500,                                                                                                                                                                                    
            detail="CUTSHORT_COOKIE env var not set. Copy from your logged-in browser session.",
        )                                                                                                                                                                                                       
 
    headers = {                                                                                                                                                                                                 
        "Cookie": cookie,                                 
        "User-Agent": (                                                                                                                                                                                         
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"                                                                                                                                                
        ),                                                
        "Accept": "application/json",                                                                                                                                                                           
        "Referer": f"{CUTSHORT_BASE}/profile/all-jobs?matchesfor={user_id}",                                                                                                                                    
    }                                                                                                                                                                                                           
                                                                                                                                                                                                                
    extra = _build_filter_params(                                                                                                                                                                               
        skills=skills,                                    
        locations=locations,
        role_type=role_type,                                                                                                                                                                                    
        remote_type=remote_type,
        min_salary=min_salary,                                                                                                                                                                                  
        max_salary=max_salary,                            
        currency=currency,
        min_exp=min_exp,
        max_exp=max_exp,                                                                                                                                                                                        
        hiring_activity=hiring_activity,
    )                                                                                                                                                                                                           
                                                          
    async with httpx.AsyncClient(
        headers=headers, timeout=20.0, follow_redirects=True
    ) as client:                                                                                                                                                                                                
        results = await asyncio.gather(
            *(_fetch_page(client, user_id, p, extra) for p in range(1, pages + 1)),                                                                                                                             
            return_exceptions=True,                                                                                                                                                                             
        )
                                                                                                                                                                                                                
    all_jobs, errors = [], []                             
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            errors.append({"page": i + 1, "error": str(r)})
            continue
        page_jobs = (                                                                                                                                                                                           
            r.get("jobs")
            or r.get("data")                                                                                                                                                                                    
            or r.get("results")                           
            or r.get("items")                                                                                                                                                                                   
            or (r if isinstance(r, list) else [])
        )                                                                                                                                                                                                       
        all_jobs.extend(page_jobs)                        
                                                                                                                                                                                                                
    return {
        "count": len(all_jobs),                                                                                                                                                                                 
        "user_id": user_id,                               
        "pages": pages,
        "filters": extra,
        "errors": errors,
        "jobs": all_jobs if raw else [_normalize(j) for j in all_jobs],                                                                                                                                         
    }