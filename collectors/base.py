"""공통 유틸리티 — DB 경로/로그/HTTP 헬퍼.

stock_chart_web 으로 이식되며, 기존 stock_db 와의 차이:
  - DB_PATH 는 환경변수 STOCK_DB 우선 (GitHub Actions 에서 /tmp 사용)
  - 로그 파일도 LOG_DIR 환경변수 + 디렉토리 자동 생성
  - DART_API_KEY 는 하드코딩 fallback 유지 (공개 키)
"""
import os, sqlite3, time, logging
from datetime import datetime

# DB 경로 — 환경변수 우선. 기본은 stock_chart_web/data/stock_db.sqlite (.gitignore)
DB_PATH = os.environ.get(
    'STOCK_DB',
    os.path.join(os.path.dirname(__file__), '..', 'data', 'stock_db.sqlite')
)
DART_API_KEY = os.environ.get('DART_API_KEY', 'bbfb92fc826e2ad707a46aca49ae7cc3aff923d3')

# 로그 디렉토리 자동 생성
_LOG_DIR = os.environ.get('LOG_DIR', os.path.join(os.path.dirname(__file__), '..', 'logs'))
os.makedirs(_LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(_LOG_DIR, 'collector.log'), encoding='utf-8'),
    ]
)
log = logging.getLogger('stock_db')

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def safe_int(v):
    try: return int(str(v).replace(',','').replace(' ','')) if v else None
    except: return None

def safe_float(v):
    try: return float(str(v).replace(',','').replace(' ','').replace('%','')) if v else None
    except: return None

def rate_limit(secs=0.5):
    time.sleep(secs)
