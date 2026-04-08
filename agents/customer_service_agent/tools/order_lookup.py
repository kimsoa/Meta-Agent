"""Tool: order_lookup"""

def get_order_status(order_id: str, db_path: str = 'orders.db') -> dict:
    """Return status and details for a given order ID."""
    import sqlite3, pathlib
    if not pathlib.Path(db_path).exists():
        return {'error': f'Database not found: {db_path}'}
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        'SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else {'error': f'Order {order_id} not found'}

