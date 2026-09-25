from sqlalchemy.ext.asyncio import AsyncSession

from app.models.merge_request import merge_request_work_items


async def set_links(db: AsyncSession, merge_request_id, work_item_ids: list) -> None:
    """Make the merge request's links exactly `work_item_ids` (GitLab's references are the truth)."""
    await db.execute(
        merge_request_work_items.delete().where(merge_request_work_items.c.merge_request_id == merge_request_id)
    )
    unique_ids = list(dict.fromkeys(work_item_ids))
    if unique_ids:
        await db.execute(
            merge_request_work_items.insert(),
            [{"merge_request_id": merge_request_id, "work_item_id": wid} for wid in unique_ids],
        )
