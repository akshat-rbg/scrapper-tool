import json                                                                                                                                                                                                     
from os import getenv                                     
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
                                                                                                                                                                                                                
router = APIRouter(prefix="/wellfound", tags=["wellfound"])                                                                                                                                                     
                                                                                                                                                                                                                
WELLFOUND_GRAPHQL = "https://wellfound.com/graphql"                                                                                                                                                             
DEFAULT_OPERATION_ID = (                                  
    "tfe/5f366cd305b4f13cf6098df75f7ff2bb92fa42b9a74cb3a3aec7bdc69c6b051e"                                                                                                                                      
)                                                                                                                                                                                                               
                                                                                                                                                                                                                
                                                                                                                                                                                                                
def _required_env(name: str) -> str:                      
    v = getenv(name)
    if not v:
        raise HTTPException(
            status_code=500,
            detail=f"{name} env var not set. Capture from a logged-in browser request.",                                                                                                                        
        )                                                                                                                                                                                                       
    return v                                                                                                                                                                                                    
                                                                                                                                                                                                                
                                                                                                                                                                                                                
def _csv_list(s: Optional[str]) -> list[str]:
    if not s:                                                                                                                                                                                                   
        return []                                         
    return [x.strip() for x in s.split(",") if x.strip()]

                                                                                                                                                                                                                
def _flatten_jobs(edges: list[dict]) -> list[dict]:
    """One startup can have multiple job listings — flatten to one entry per listing."""                                                                                                                        
    out = []                                              
    for edge in edges or []:                                                                                                                                                                                    
        if not isinstance(edge, dict):
            continue                                                                                                                                                                                            
        node = edge.get("node") or edge                   
        if not isinstance(node, dict):                                                                                                                                                                          
            continue
                                                                                                                                                                                                                
        is_promoted = node.get("__typename") == "PromotedResult"
        startup = node.get("promotedStartup") if is_promoted else node
        if not isinstance(startup, dict):                                                                                                                                                                       
            continue
                                                                                                                                                                                                                
        for listing in startup.get("highlightedJobListings") or []:                                                                                                                                             
            if isinstance(listing, dict):
                out.append({"listing": listing, "startup": startup, "is_promoted": is_promoted})                                                                                                                
    return out                                                                                                                                                                                                  

                                                                                                                                                                                                                
def _normalize(item: dict) -> dict:                       
    listing = item["listing"]
    startup = item["startup"]
    listing_id = listing.get("id")
    listing_slug = listing.get("slug")                                                                                                                                                                          

    return {                                                                                                                                                                                                    
        "id": listing_id,                                 
        "title": listing.get("title"),
        "primary_role": listing.get("primaryRoleTitle"),                                                                                                                                                        
        "slug": listing_slug,
        "description": listing.get("description"),                                                                                                                                                              
        "compensation": listing.get("compensation"),      
        "equity": listing.get("equity"),                                                                                                                                                                        
        "job_type": listing.get("jobType"),
        "remote": listing.get("remote"),                                                                                                                                                                        
        "remote_kind": (listing.get("remoteConfig") or {}).get("kind"),
        "wfh_flexible": (listing.get("remoteConfig") or {}).get("wfhFlexible"),                                                                                                                                 
        "locations": listing.get("locationNames") or [],                                                                                                                                                        
        "accepted_remote_locations": listing.get("acceptedRemoteLocationNames") or [],                                                                                                                          
        "posted_at": listing.get("liveStartAt"),                                                                                                                                                                
        "last_responded_at": listing.get("lastRespondedAt"),
        "reposted": listing.get("reposted"),                                                                                                                                                                    
        "auto_posted": listing.get("autoPosted"),         
        "ats_source": listing.get("atsSource"),                                                                                                                                                                 
        "is_bookmarked": listing.get("isBookmarked"),                                                                                                                                                           
        "user_applied": listing.get("currentUserApplied"),
        "url": (                                                                                                                                                                                                
            f"https://wellfound.com/jobs/{listing_id}-{listing_slug}"
            if listing_id and listing_slug                                                                                                                                                                      
            else None                                     
        ),
        "company": {                                                                                                                                                                                            
            "id": startup.get("startupId") or startup.get("id"),
            "name": startup.get("name"),                                                                                                                                                                        
            "slug": startup.get("slug"),                  
            "logo": startup.get("logoUrl"),
            "size": startup.get("companySize"),                                                                                                                                                                 
            "tagline": startup.get("highConcept"),
            "url": (                                                                                                                                                                                            
                f"https://wellfound.com/company/{startup.get('slug')}"
                if startup.get("slug")                                                                                                                                                                          
                else None
            ),                                                                                                                                                                                                  
            "badges": [                                   
                b.get("label")
                for b in (startup.get("badges") or [])
                if isinstance(b, dict) and b.get("label")                                                                                                                                                       
            ],
            "locations": [                                                                                                                                                                                      
                t.get("displayName")                      
                for t in (startup.get("locationTaggings") or [])
                if isinstance(t, dict) and t.get("displayName")                                                                                                                                                 
            ],
        },                                                                                                                                                                                                      
        "is_promoted": item["is_promoted"],               
        "news": (
            {
                "headline": startup.get("newsStoryHeadline"),
                "url": startup.get("newsStoryUrl"),                                                                                                                                                             
                "source": startup.get("newsStorySource"),
                "snippet": startup.get("newsStorySnippet"),                                                                                                                                                     
                "thumbnail": startup.get("newsStoryThumbnailUrl"),                                                                                                                                              
                "published_date": startup.get("newsStoryPublishedDate"),
            }                                                                                                                                                                                                   
            if startup.get("newsStoryHeadline")           
            else None                                                                                                                                                                                           
        ),                                                
    }


@router.get("/jobs")
async def get_jobs(
    page: int = Query(1, ge=1, le=20),                                                                                                                                                                          
    location_ids: Optional[str] = Query(
        None, description="Comma-separated Wellfound location tag IDs, e.g. '1904,1622'"                                                                                                                        
    ),                                                                                                                                                                                                          
    role_ids: Optional[str] = Query(                                                                                                                                                                            
        None, description="Comma-separated role tag IDs, e.g. '151647,151645'"                                                                                                                                  
    ),                                                                                                                                                                                                          
    skill_ids: Optional[str] = Query(
        None, description="Comma-separated skill tag IDs (if your filter capture includes them)"                                                                                                                
    ),                                                                                                                                                                                                          
    job_types: str = Query(
        "full_time", description="Comma-separated: full_time,internship,contract,part_time"                                                                                                                     
    ),                                                                                                                                                                                                          
    remote: str = Query(
        "REMOTE_OPEN", description="REMOTE_OPEN | REMOTE_ONLY | ONSITE_ONLY"                                                                                                                                    
    ),                                                                                                                                                                                                          
    mostly_or_fully_remote: bool = Query(False),                                                                                                                                                                
    min_exp: Optional[int] = Query(None, ge=0, le=30),                                                                                                                                                          
    max_exp: Optional[int] = Query(None, ge=0, le=30),                                                                                                                                                          
    include_no_experience: bool = Query(True),                                                                                                                                                                  
    include_no_salary: bool = Query(True),                                                                                                                                                                      
    extra_variables: Optional[str] = Query(               
        None,                                                                                                                                                                                                   
        description="JSON merged into filterConfigurationInput (for fields we don't expose)",
    ),                                                                                                                                                                                                          
    raw: bool = Query(False),                             
):                                                                                                                                                                                                              
    cookie = _required_env("WELLFOUND_COOKIE")            
    apollo_signature = _required_env("WELLFOUND_APOLLO_SIGNATURE")                                                                                                                                              
    cfp_token = _required_env("WELLFOUND_CFP_TOKEN")                                                                                                                                                            
    operation_id = getenv("WELLFOUND_OPERATION_ID", DEFAULT_OPERATION_ID)                                                                                                                                       
                                                                                                                                                                                                                
    filter_config = {                                                                                                                                                                                           
        "page": page,                                                                                                                                                                                           
        "locationTagIds": _csv_list(location_ids),        
        "roleTagIds": _csv_list(role_ids),                                                                                                                                                                      
        "includeJobsWithoutExperience": include_no_experience,
        "includeJobsWithoutSalary": include_no_salary,                                                                                                                                                          
        "jobTypes": _csv_list(job_types),                 
        "remotePreference": remote,                                                                                                                                                                             
        "mostlyOrFullyRemote": mostly_or_fully_remote,    
        "equity": {"min": None, "max": None},                                                                                                                                                                   
        "yearsExperience": {"min": min_exp, "max": max_exp},                                                                                                                                                    
    }
                                                                                                                                                                                                                
    if skill_ids:                                         
        filter_config["skillTagIds"] = _csv_list(skill_ids)                                                                                                                                                     
                                                          
    if extra_variables:
        try:
            filter_config.update(json.loads(extra_variables))
        except json.JSONDecodeError as e:                                                                                                                                                                       
            raise HTTPException(status_code=400, detail=f"Bad extra_variables JSON: {e}")
                                                                                                                                                                                                                
    body = {                                              
        "operationName": "JobSearchResultsX",                                                                                                                                                                   
        "variables": {"filterConfigurationInput": filter_config},                                                                                                                                               
        "extensions": {"operationId": operation_id},
    }                                                                                                                                                                                                           
                                                          
    headers = {                                                                                                                                                                                                 
        "accept": "*/*",                                  
        "accept-language": "en-US,en;q=0.9",
        "apollographql-client-name": "talent-web",
        "content-type": "application/json",                                                                                                                                                                     
        "Cookie": cookie,
        "origin": "https://wellfound.com",                                                                                                                                                                      
        "referer": "https://wellfound.com/jobs",          
        "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',                                                                                                                        
        "sec-ch-ua-mobile": "?0",                                                                                                                                                                               
        "sec-ch-ua-platform": '"macOS"',
        "user-agent": (                                                                                                                                                                                         
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "                                                                                                                               
            "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
        ),                                                                                                                                                                                                      
        "x-apollo-operation-name": "JobSearchResultsX",   
        "x-apollo-signature": apollo_signature,                                                                                                                                                                 
        "x-wf-cfp": cfp_token,                            
        "x-requested-with": "XMLHttpRequest",                                                                                                                                                                   
    }                                                     
                                                                                                                                                                                                                
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:                                                                                                                                
        resp = await client.post(WELLFOUND_GRAPHQL, headers=headers, json=body)
                                                                                                                                                                                                                
    if resp.status_code in (401, 403):                    
        raise HTTPException(                                                                                                                                                                                    
            status_code=401,                              
            detail=(                                                                                                                                                                                            
                "Wellfound auth rejected. Refresh WELLFOUND_COOKIE, "
                "WELLFOUND_APOLLO_SIGNATURE, WELLFOUND_CFP_TOKEN — they expire."                                                                                                                                
            ),                                                                                                                                                                                                  
        )                                                                                                                                                                                                       
    if resp.status_code == 429:                                                                                                                                                                                 
        raise HTTPException(status_code=429, detail="Wellfound rate-limited")
    if resp.status_code != 200:                                                                                                                                                                                 
        raise HTTPException(
            status_code=502,                                                                                                                                                                                    
            detail=f"Wellfound returned {resp.status_code}: {resp.text[:200]}",
        )                                                                                                                                                                                                       

    payload = resp.json()                                                                                                                                                                                       
    if "errors" in payload:                               
        raise HTTPException(
            status_code=502, detail=f"GraphQL errors: {payload['errors'][:1]}"                                                                                                                                  
        )                                                                                                                                                                                                       
                                                                                                                                                                                                                
    search = (                                                                                                                                                                                                  
        (payload.get("data") or {}).get("talent", {}).get("jobSearchResults") or {}
    )
    edges = (search.get("startups") or {}).get("edges") or []
    flattened = _flatten_jobs(edges)                                                                                                                                                                            

    return {                                                                                                                                                                                                    
        "count": len(flattened),                          
        "page": page,                                                                                                                                                                                           
        "has_next_page": search.get("hasNextPage", False),
        "raw_query": search.get("rawQuery"),
        "filters": filter_config,                                                                                                                                                                               
        "jobs": (
            [{"listing": f["listing"], "startup": f["startup"], "is_promoted": f["is_promoted"]} for f in flattened]                                                                                            
            if raw                                                                                                                                                                                              
            else [_normalize(f) for f in flattened]
        ),                                                                                                                                                                                                      
    }