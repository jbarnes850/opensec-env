import sqlite3
from pathlib import Path

from sim.log_compiler import compile_seed


def test_compile_logs(tmp_path: Path):
    db_path = tmp_path / "seed-001.db"
    compile_seed(Path("data/seeds/sample_seed.json"), db_path)

    with sqlite3.connect(db_path) as conn:
        email_count = conn.execute("SELECT COUNT(*) FROM email_logs").fetchone()[0]
        auth_count = conn.execute("SELECT COUNT(*) FROM auth_logs").fetchone()[0]
        net_count = conn.execute("SELECT COUNT(*) FROM netflow").fetchone()[0]
        proc_count = conn.execute("SELECT COUNT(*) FROM process_events").fetchone()[0]
        alert_count = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        inj_count = conn.execute("SELECT COUNT(*) FROM prompt_injections").fetchone()[0]

    assert email_count == 1
    assert auth_count == 1
    assert net_count == 1
    assert proc_count == 1
    assert alert_count == 1
    assert inj_count == 2
