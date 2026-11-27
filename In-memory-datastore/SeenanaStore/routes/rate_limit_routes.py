from typing import Any

from fastapi import APIRouter, HTTPException, Request


router = APIRouter()


@router.get("/admin/rate-limit")
async def get_rate_limit_policy(request: Request):
    return request.app.state.rate_limiter.get_policy()


@router.put("/admin/rate-limit")
async def update_rate_limit_policy(
    policy: dict[str, Any],
    request: Request,
):
    try:
        return request.app.state.rate_limiter.update_policy(**policy)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
