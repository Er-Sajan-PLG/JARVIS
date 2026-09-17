"""REST API routes for morning brief."""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.adapters.http.router import validate_api_key
from app.integrations.brief import BriefConfig, BriefService

logger = logging.getLogger(__name__)

brief_router = APIRouter(
    prefix="/api/v1/brief",
    tags=["Morning Brief"],
    dependencies=[Depends(validate_api_key)]
)


@brief_router.get("/")
async def get_brief() -> dict[str, Any]:
    """Generate and return the morning brief."""
    config = BriefConfig.from_env()
    service = BriefService(config)
    
    brief = await service.generate_brief()
    return brief


@brief_router.post("/deliver")
async def deliver_brief() -> dict[str, Any]:
    """Generate and deliver the morning brief."""
    config = BriefConfig.from_env()
    service = BriefService(config)
    
    brief = await service.generate_brief()
    results = await service.deliver(brief)
    
    return {"success": True, "brief": brief, "delivery_results": results}


@brief_router.get("/status")
async def brief_status() -> dict[str, Any]:
    """Get brief service status."""
    config = BriefConfig.from_env()
    return {
        "enabled": config.enabled,
        "time": config.time,
        "delivery_channels": config.delivery_channels,
    }
