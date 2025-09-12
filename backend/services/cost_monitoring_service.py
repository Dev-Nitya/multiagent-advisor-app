"""
Cost monitoring service for tracking OpenAI usage and enforcing budgets.

This service provides comprehensive cost tracking and budget management
for OpenAI API usage across the entire application.

Key Features:
- Real-time cost tracking per user/session
- Budget enforcement with automatic cutoffs
- Cost analytics and reporting
- Alert system for budget thresholds

Integration Points:
- Uses token_calculator.py for accurate cost estimation
- Integrates with cost_limits.py for budget configuration
- Provides middleware integration points
"""

import logging
from time import time
from datetime import datetime

from config.database import get_db
from models.user import UserBudget

logger = logging.getLogger(__name__)

class CostMonitoringService:
    """
    This is a "Budget Manager" for our app.
    
    It does 4 simple things:
    1. Checks if user can afford a request (before spending money)
    2. Records how much was actually spent (after the request)
    3. Sends alerts when budget is running low
    4. Stores all this data so it persists between requests
    """

    def __init__(self):
        logger.info('💰 Initializing CostMonitoringService')
     
    def can_user_afford_this_request(self, user_id, estimated_cost, user_tier):
        """
        SIMPLE QUESTION: Can this user afford this AI request?
        
        This is like checking your bank balance before buying something.
        
        Steps:
        1. Get user's budget limits (how much they're allowed to spend)
        2. Get user's current spending (how much they've already spent)
        3. Calculate remaining budget
        4. Check if estimated cost fits within remaining budget
        """

        if not estimated_cost or estimated_cost.get('total_cost_usd', 0) <= 0:
            return True, "No cost estimated"
        
        total_cost = estimated_cost['total_cost_usd']

        try:
            db = next(get_db())

            user_budget = db.query(UserBudget).filter(UserBudget.user_id == user_id).first()
            if not user_budget:
                db.close()
                return False, "No budget configuration found for user"
            

            # Check if daily budget allows this request
            daily_remaining = user_budget.daily_limit_usd - user_budget.daily_spent_usd
            if total_cost > daily_remaining:
                db.close()
                return False, f"Daily budget exceeded. Remaining: ${daily_remaining:.2f}, Request: ${total_cost:.2f}"
            
            # Check if monthly budget allows this request  
            monthly_remaining = user_budget.monthly_limit_usd - user_budget.monthly_spent_usd
            if total_cost > monthly_remaining:
                db.close()
                return False, f"Monthly budget exceeded. Remaining: ${monthly_remaining:.2f}, Request: ${total_cost:.2f}"

            db.close()
            return True, "Budget check passed"
            
        except Exception as e:
            logger.info(f"Budget check error for user {user_id}: {e}")
            return False, "Budget check failed"
        
        finally:
            db.close()

    def record_money_spent(self, user_id, actual_cost):
        """
        SIMPLE ACTION: Record that money was spent.
        
        This is like updating your bank account after a purchase.
        
        Steps:
        1. Add the cost to user's daily spending
        2. Add the cost to user's monthly spending  
        3. Check if we should send any alerts
        """

        if not actual_cost or actual_cost <= 0:
            logger.debug(f"No cost to record for user {user_id}")
            return True

        try:
            # Get database session
            db = next(get_db())
            
            # Find user's budget record
            user_budget = db.query(UserBudget).filter(UserBudget.user_id == user_id).first()
            logger.info('💰 Recording cost for user %s: $%.4f', user_id, actual_cost)
            
            if not user_budget:
                logger.warning(f"No budget record found for user {user_id} when recording ${actual_cost:.4f}")
                db.close()
                return False
            
            # Check if we need to reset daily/monthly counters
            current_date = datetime.utcnow().date()
            current_month = datetime.utcnow().replace(day=1).date()

            # Reset daily spending if it's a new day
            if user_budget.daily_reset_date and user_budget.daily_reset_date.date() < current_date:
                logger.info(f"Resetting daily spending for user {user_id} (new day)")
                user_budget.daily_spent_usd = 0.0
                user_budget.daily_reset_date = datetime.utcnow()
            
            # Reset monthly spending if it's a new month
            if user_budget.monthly_reset_date and user_budget.monthly_reset_date.date() < current_month:
                logger.info(f"Resetting monthly spending for user {user_id} (new month)")
                user_budget.monthly_spent_usd = 0.0
                user_budget.monthly_reset_date = datetime.utcnow()

            # Add the cost to current spending
            user_budget.daily_spent_usd += actual_cost
            user_budget.monthly_spent_usd += actual_cost
            user_budget.updated_at = datetime.utcnow()
            
            # Commit the changes
            db.commit()

            logger.info(f"💰 Recorded ${actual_cost:.4f} for user {user_id}. "
                       f"Daily: ${user_budget.daily_spent_usd:.2f}/${user_budget.daily_limit_usd:.2f}, "
                       f"Monthly: ${user_budget.monthly_spent_usd:.2f}/${user_budget.monthly_limit_usd:.2f}")
            
            # Check if we should send alerts

            self._check_budget_alerts(user_budget)

            db.close()
            return True
            
        except Exception as e:
            logger.error(f"Error recording ${actual_cost:.4f} for user {user_id}: {e}")
            if 'db' in locals():
                db.rollback()
                db.close()
            return False
        
        finally:
            db.close()

    def _check_budget_alerts(self, user_budget: UserBudget):
        """
        UPDATED: Check if alerts needed based on UserBudget data
        
        SIMPLE EXPLANATION:
        Look at user's spending percentage and send alerts:
        - 75% of budget used → WARNING
        - 90% of budget used → CRITICAL
        """
        
        try:
            # Calculate daily budget usage percentage
            daily_usage_percent = (user_budget.daily_spent_usd / user_budget.daily_limit_usd) * 100 if user_budget.daily_limit_usd > 0 else 0
            monthly_usage_percent = (user_budget.monthly_spent_usd / user_budget.monthly_limit_usd) * 100 if user_budget.monthly_limit_usd > 0 else 0
            
            # Send alerts based on usage
            if daily_usage_percent >= 90:
                self._send_alert(user_budget.user_id, "CRITICAL", 
                               f"90% of daily budget used (${user_budget.daily_spent_usd:.2f}/${user_budget.daily_limit_usd:.2f})")
            elif daily_usage_percent >= 75:
                self._send_alert(user_budget.user_id, "WARNING", 
                               f"75% of daily budget used (${user_budget.daily_spent_usd:.2f}/${user_budget.daily_limit_usd:.2f})")
            
            if monthly_usage_percent >= 90:
                self._send_alert(user_budget.user_id, "CRITICAL", 
                               f"90% of monthly budget used (${user_budget.monthly_spent_usd:.2f}/${user_budget.monthly_limit_usd:.2f})")
                
        except Exception as e:
            logger.error(f"Error checking budget alerts for user {user_budget.user_id}: {e}")

    def _send_alert(self, user_id, level, message):
        """
        SIMPLE NOTIFICATION: Tell the user about their budget status.
        
        This is like sending a text message alert.
        For now, we just log it, but later we could email/SMS.
        """
        print(f"ALERT for {user_id}: {level} - {message}")
        
        # Store alert in Redis so UI can show it
        alert_data = {
            "user_id": user_id,
            "level": level,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }

        alert_key = f"alert:{user_id}:{int(time.time())}"

cost_monitoring_service = CostMonitoringService()