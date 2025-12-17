# app/tasks/filter_tasks.py
import uuid
from datetime import datetime
from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.utils.call_gpt import call_gpt
from app.utils.models import Inputs, Results, Recipient_lists
from app.utils.db import get_db

logger = get_task_logger(__name__)

@celery_app.task(bind=True, name="filter.process_external_request")
def process_external_request_task(self, input_id: str, user_id: str, db: Session) -> dict:
    try:
        input_row = (
            db.query(Inputs)
            .filter(Inputs.id == input_id)
            .first()
        )
        if not input_row:
            raise ValueError(f"Input not found: {input_id}")

        payload = input_row.input_data or {}

        recipient = None
        if getattr(input_row, "recipient_id", None):
            rec = (
                db.query(Recipient_lists)
                .filter(
                    Recipient_lists.id == input_row.recipient_id,
                    Recipient_lists.user_id == user_id,
                )
                .first()
            )
            if rec:
                recipient = {"name": rec.recipient_name, "group": rec.recipient_group}

        result_data = call_gpt(payload.get("data"), payload.get("guide"), recipient)

        result_row = Results(
            id=uuid.uuid4(),
            result_data=result_data,          # dict
            time_returned=datetime.utcnow(),
            input_id=input_row.id,
        )

        db.add(result_row)
        db.commit()
        db.refresh(result_row)

        return result_row.result_data  # ExternalResultSchema.result에 해당하는 dict

    except Exception:
        db.rollback()
        logger.exception("Task failed (input_id=%s)", input_id)
        raise
    finally:
        db.close()
