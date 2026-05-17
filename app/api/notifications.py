"""
Notifications API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import get_db
from app.models.user import User
from app.models.notification import Notification
from app.api.payments import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("/list")
@limiter.limit("60/minute")
async def list_notifications(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List notifications with pagination.
    
    Rate limit: 60 requests per minute
    """
    try:
        query = db.query(Notification).filter(
            Notification.user_id == current_user.id
        )
        
        if unread_only:
            query = query.filter(Notification.is_read == False)
        
        total = query.count()
        
        notifications = query.order_by(
            Notification.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        notification_list = []
        for notif in notifications:
            notification_list.append({
                "id": str(notif.id),
                "type": notif.type,
                "title": notif.title,
                "message": notif.message,
                "action_url": notif.action_url,
                "is_read": notif.is_read,
                "created_at": notif.created_at.isoformat()
            })
        
        return {
            "notifications": notification_list,
            "total": total,
            "unread_count": db.query(Notification).filter(
                Notification.user_id == current_user.id,
                Notification.is_read == False
            ).count()
        }
    
    except Exception as e:
        logger.error(f"Notifications list error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch notifications"
        )


@router.post("/{notification_id}/read")
@limiter.limit("60/minute")
async def mark_notification_read(
    request: Request,
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark notification as read.
    
    Rate limit: 60 requests per minute
    """
    try:
        notification = db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        ).first()
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        notification.is_read = True
        db.commit()
        
        return {"message": "Notification marked as read"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mark notification error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notification as read"
        )


@router.post("/mark-all-read")
@limiter.limit("20/minute")
async def mark_all_notifications_read(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark all notifications as read.
    
    Rate limit: 20 requests per minute
    """
    try:
        db.query(Notification).filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False
        ).update({"is_read": True})
        
        db.commit()
        
        return {"message": "All notifications marked as read"}
    
    except Exception as e:
        logger.error(f"Mark all read error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark all notifications as read"
        )
