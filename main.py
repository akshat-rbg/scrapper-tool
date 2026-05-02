from os import getenv                                                                                                                                                                                           
                                                                                                                                                                                                                
from dotenv import load_dotenv
load_dotenv()                                                                                                                                                                                                   
                                                          
from fastapi import FastAPI                                                                                                                                                                                     

from browser import lifespan, get_browser                                                                                                                                                                       
from naukri_scraper import router as naukri_router        
from linkedin_scraper import router as linkedin_router                                                                                                                                                          
from cutshort_scraper import router as cutshort_router
from hirist_scraper import router as hirist_router                                                                                                                                                              
from wellfound_scraper import router as wellfound_router

app = FastAPI(title="Job Scrapers", version="1.0.0", lifespan=lifespan)                                                                                                                                         
app.include_router(naukri_router)                         
app.include_router(linkedin_router)                                                                                                                                                                             
app.include_router(cutshort_router)                       
app.include_router(hirist_router)                                                                                                                                                                               
app.include_router(wellfound_router)
                                                                                                                                                                                                                
@app.get("/health")                                       
async def health():
    return {"status": "ok", "browser_ready": get_browser() is not None}
                                                                                                                                                                                                                

if __name__ == "__main__":                                                                                                                                                                                      
    import uvicorn                                        
    uvicorn.run(app, host="0.0.0.0", port=int(getenv("PORT", "8000")))