"""Queue depth helper."""

def estimate_queue_depth(visitor_ids_in_queue: set[str]) -> int:
    return len(visitor_ids_in_queue)
