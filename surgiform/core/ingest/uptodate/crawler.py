import asyncio
import os
import dotenv
import json
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Set
from urllib.parse import urlparse
from urllib.parse import urlunparse
from urllib.parse import ParseResult
from playwright.async_api import async_playwright
from tqdm.asyncio import tqdm

dotenv.load_dotenv()

ID = os.getenv("UPTODATE_ID")
PW = os.getenv("UPTODATE_PW")


def strip_fragment(url: str) -> str:
    """#fragment 제거"""
    pr: ParseResult = urlparse(url)
    pr = pr._replace(fragment="")
    return urlunparse(pr)


def safe_filename(title: str, max_length: int = 200) -> str:
    """제목을 안전한 파일명으로 변환"""
    # HTML 태그 제거
    title = re.sub(r'<[^>]+>', '', title)
    
    # 파일시스템에서 문제가 될 수 있는 문자들 제거/변환
    title = re.sub(r'[<>:"/\\|?*]', '', title)  # Windows 금지 문자
    title = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', title)  # 제어 문자
    
    # 연속된 공백을 하나로, 앞뒤 공백 제거
    title = re.sub(r'\s+', ' ', title).strip()
    
    # 공백을 언더스코어로 변환
    title = title.replace(' ', '_')
    
    # 점으로 시작하는 파일명 방지 (숨김 파일)
    if title.startswith('.'):
        title = '_' + title[1:]
    
    # 길이 제한
    if len(title) > max_length:
        title = title[:max_length]
    
    # 빈 문자열 방지
    if not title:
        title = "untitled"
    
    return title


def is_allowed_path(path, target_field: str | None = None):
    if not path.startswith('/contents/'):
        return False
    
    # 제외할 키워드들
    exclude_keywords = [
        'image',
        'calculators',
        'whats-new',
        'search',
        'authors-and-editors',
        'practice-changing-updates',
        'pathways',
    ]
    if any(keyword in path for keyword in exclude_keywords):
        return False
    
    # /contents/table-of-contents 단독은 제외
    if path == '/contents/table-of-contents':
        return False
    
    # /contents/table-of-contents/general-surgery/~ 가 아니면 제외
    if target_field:
        if path.startswith('/contents/table-of-contents/'):
            if not path.startswith(f'/contents/table-of-contents/{target_field}/'):
                return False
    
    # 일반 topic 링크는 모두 허용
    return True


def is_internal_contents(url: str, domain: str, target_field: str | None = None) -> bool:
    """UpToDate /contents/ 내부 링크 + avoid 패턴 제외"""
    try:
        pr = urlparse(url)
        if pr.scheme not in {"http", "https"} or pr.netloc != domain:
            return False
        if not pr.path.startswith("/contents/"):
            return False
        return is_allowed_path(pr.path, target_field)
    except Exception:
        return False


# async def login_uptodate_manual(page, id, pw) -> bool:
#     """UpToDate 수동 로그인"""
#     try:
#         print("🔐 로그인 페이지로 이동 중...")
#         await page.goto("https://www.uptodate.com/login", wait_until="networkidle")
#         
#         print("="*60)
#         print("📝 수동 로그인이 필요합니다!")
#         print("1. 브라우저에서 사용자명과 비밀번호를 입력하세요")
#         print(f"   ID: {id}")
#         print(f"   PW: {pw}")
#         print("2. 로그인 버튼을 클릭하세요")
#         print("3. 2FA가 있다면 코드를 입력하세요")
#         print("4. 로그인이 완료되면 아무 키나 누르고 Enter를 눌러주세요")
#         print("="*60)
#         
#         # 사용자 입력 대기
#         input("로그인 완료 후 Enter를 눌러주세요...")
#         return True
#             
#     except Exception as e:
#         print(f"❌ 로그인 과정에서 오류: {e}")
#         return False


async def process_single_page(
    page, 
    url: str, 
    out_path: Path, 
    visited: Set[str], 
    queue: list[str], 
    domain: str, 
    target_field: str | None,
    visited_lock: asyncio.Lock,
    queue_lock: asyncio.Lock,
    browser_lock: asyncio.Lock,
    browser_context,
    saved_count_lock: asyncio.Lock,
    saved_pbar: tqdm,
    queue_pbar: tqdm,
    saved_count: dict,  # dict로 전달하여 참조로 수정 가능하게 함
    logger: logging.Logger,
    worker_id: int,
    playwright_instance,
    user_data_dir: str,
    headless: bool,
    separate_windows: bool,
    browser_contexts: list
) -> tuple[bool, any, any]:  # (성공여부, 새로운 컨텍스트, 새로운 페이지)
    """단일 페이지 처리 워커 함수"""
    try:
        logger.info(f"페이지 접속: {url}")
        await page.goto(url, wait_until="networkidle", timeout=60_000)
        
        # 페이지 로드 후 검색 페이지로 리다이렉트 되었는지 확인
        current_url = page.url
        if "/contents/search" in current_url or "/login" in current_url:
            logger.warning(f"워커 {worker_id}: 리다이렉트 감지됨. 브라우저 창 재시작...")
            
            async with browser_lock:
                # 현재 페이지와 컨텍스트 닫기
                await page.close()
                if separate_windows:
                    await browser_context.close()
                    
                    # 새로운 브라우저 컨텍스트 생성
                    new_context = await playwright_instance.chromium.launch_persistent_context(
                        user_data_dir=f"{user_data_dir}_{worker_id}",
                        headless=headless
                    )
                    
                    # browser_contexts 리스트 업데이트
                    browser_contexts[worker_id] = new_context
                    browser_context = new_context
                    logger.info(f"워커 {worker_id}: 새로운 브라우저 창 생성 완료")
                else:
                    # 탭 모드에서는 컨텍스트는 그대로 두고 페이지만 재생성
                    pass
                
                # 새로운 페이지 생성
                page = await browser_context.new_page()
            
            # 원래 URL로 다시 이동
            await page.goto(url, wait_until="networkidle", timeout=60_000)
            
    except Exception as e:
        logger.error(f"페이지 로드 실패: {e}")
        return False, browser_context, page

    has_topic = await page.evaluate(
        """
        () => {
            // 1️⃣ id='topic-title' 또는 'topicTitle' 이 존재하면 바로 true
            if (document.getElementById('topic-title') ||
                document.getElementById('topicTitle') ||
                document.getElementById('topicOutline') ||
                document.getElementById('topicArticle') ||
                document.getElementById('topicContent')){
                return true;
            }

            // 2️⃣ 기존 탐색 로직 유지
            const nav = document.querySelector(
                'main nav, #topic-outline, .topic-content'
            );
            if (!nav) return false;

            return /\\bTopic\\b/i.test(nav.textContent || '');
        }
        """
    )

    if has_topic:
        title = await page.title()
        
        # 파일명 생성 및 파일 존재 여부 확인
        filename = safe_filename(title) + ".json"
        file_path = out_path / filename
        
        if file_path.exists():
            logger.info(f"이미 존재하는 파일 스킵: {filename}")
            return False, browser_context, page
        
        logger.info(f"토픽 페이지 발견: {title}")
        try:
            content = await page.locator("#topicContent").inner_html()
        except Exception as e:
            logger.warning(f"콘텐츠 추출 실패: {e}")
            content = ""

        data = {
            "url": url,
            "title": title,
            "content": content
        }

        # 개별 JSON 파일로 저장
        try:
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"파일 저장 완료: {filename}")
            
            # 저장 성공시 progress bar 업데이트
            async with saved_count_lock:
                saved_count[filename] = 1
                saved_pbar.update(1)
            
            return True, browser_context, page
        except Exception as e:
            logger.error(f"파일 저장 실패: {e}")
            return False, browser_context, page
        
        return False, browser_context, page

    # 2) 본문이 없으면 내부 링크 수집 → 큐
    try:
        links = await page.eval_on_selector_all(
            'a[href^="/contents/"]',
            'els => els.map(e => e.href)'
        )
        
        new_links = []
        for href in links:
            href = strip_fragment(href)
            if is_internal_contents(href, domain, target_field):
                async with visited_lock:
                    if href not in visited:
                        new_links.append(href)
        
        if new_links:
            async with queue_lock:
                queue.extend(new_links)
                # 새로운 링크 추가시 progress bar 업데이트
                queue_pbar.update(len(new_links))
            logger.info(f"새로운 링크 {len(new_links)}개 발견하여 큐에 추가")
                
    except Exception as e:
        logger.error(f"링크 수집 실패: {e}")

    return False, browser_context, page


async def crawl_uptodate_streaming(
        out_path: Path,
        base_url: str = "https://www.uptodate.com/contents/table-of-contents/",
        target_field: str | None = None,
        domain: str = "www.uptodate.com",
        headless: bool = True,
        clear_cache: bool = False,
        max_concurrent: int = 5,  # 동시 처리할 페이지 수
        separate_windows: bool = False  # True면 각각 별도 창, False면 탭으로
):
    _url = f"{base_url}/{target_field}" if target_field else base_url
    visited: Set[str] = set()
    queue: list[str] = [_url]
    
    # out_path를 디렉토리로 처리
    out_path.mkdir(parents=True, exist_ok=True)
    
    # 로거 설정
    log_file = out_path / f"crawler_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logger = setup_logger(log_file)
    logger.info(f"크롤링 시작: {_url}")
    
    # 동시성 제어를 위한 락과 세마포어
    visited_lock = asyncio.Lock()
    queue_lock = asyncio.Lock()
    browser_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(max_concurrent)
    
    # 활성 워커 추적을 위한 변수들
    active_workers = 0
    active_workers_lock = asyncio.Lock()
    shutdown_event = asyncio.Event()
    last_activity_time = asyncio.get_event_loop().time()
    activity_lock = asyncio.Lock()
    IDLE_TIMEOUT = 30  # 30초 동안 모든 워커가 idle이면 종료
    
    # Progress bar 추적을 위한 변수들
    saved_count = {}
    saved_count_lock = asyncio.Lock()
    
    # Progress bars 초기화
    visited_pbar = tqdm(desc="📋 Visited", unit="pages", position=0, leave=True)
    queue_pbar = tqdm(desc="📝 Queue", unit="pages", position=1, leave=True)
    saved_pbar = tqdm(desc="💾 Saved", unit="files", position=2, leave=True)
    
    # 초기 큐 크기 설정
    queue_pbar.total = len(queue)
    queue_pbar.update(len(queue))

    playwright = await async_playwright().start()
    
    # 💾 user_data_dir에 프로필을 저장합니다
    user_data_dir = "./uptodate_user_profile"
    
    # 캐시 초기화 요청이 있으면 프로필 디렉토리 삭제
    profile_path = Path(user_data_dir)
    if clear_cache and profile_path.exists():
        import shutil
        logger.info(f"캐시 초기화: {user_data_dir} 삭제 중...")
        shutil.rmtree(profile_path)
        logger.info("캐시가 초기화되었습니다.")
    
    # 프로필 디렉토리 상태 확인
    if profile_path.exists():
        logger.info(f"기존 프로필 디렉토리 발견: {user_data_dir}")
        # 프로필 내용 확인
        profile_files = list(profile_path.glob("*"))
        logger.info(f"   프로필 파일 개수: {len(profile_files)}")
    else:
        logger.info(f"새로운 프로필 디렉토리 생성 예정: {user_data_dir}")
    
    window_type = "별도 창" if separate_windows else "탭"
    logger.info(f"브라우저 시작 중... (headless: {headless}, 동시처리: {max_concurrent}개 {window_type})")
    
    if separate_windows:
        # 별도 창 모드: 각 워커마다 독립된 브라우저 인스턴스
        browser_contexts = []
        for i in range(max_concurrent):
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=f"{user_data_dir}_{i}",  # 각각 다른 프로필
                headless=headless
            )
            browser_contexts.append(context)
    else:
        # 탭 모드: 하나의 브라우저에서 여러 탭
        browser_context = await playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless
        )

    async def worker(worker_id: int = 0):
        """워커 함수: 큐에서 URL을 가져와서 처리"""
        nonlocal active_workers, last_activity_time, saved_count
        
        if separate_windows:
            context = browser_contexts[worker_id]
            page = await context.new_page()
            current_context = context
        else:
            page = await browser_context.new_page()
            current_context = browser_context
        
        logger.info(f"워커 {worker_id} 시작")
        
        try:
            while not shutdown_event.is_set():
                # 큐에서 URL 가져오기
                url = None
                async with queue_lock:
                    if queue:
                        url = strip_fragment(queue.pop(0))
                        # 큐에서 제거했으므로 progress bar 업데이트
                        queue_pbar.update(-1)
                        # 활동 시간 업데이트
                        async with activity_lock:
                            last_activity_time = asyncio.get_event_loop().time()
                
                if url is None:
                    # 큐가 비어있으면 잠시 대기 (30초 타임아웃은 별도 태스크에서 처리)
                    await asyncio.sleep(2)
                    continue
                
                # 방문 체크
                async with visited_lock:
                    if url in visited:
                        continue
                    visited.add(url)
                    # visited에 추가했으므로 progress bar 업데이트
                    visited_pbar.update(1)
                
                # 활성 워커 수 증가 및 활동 시간 업데이트
                async with active_workers_lock:
                    active_workers += 1
                async with activity_lock:
                    last_activity_time = asyncio.get_event_loop().time()
                
                try:
                    # 세마포어로 동시 처리 수 제한
                    async with semaphore:
                        # 페이지 처리 및 저장 여부 확인
                        saved, updated_context, new_page = await process_single_page(
                            page, url, out_path, visited, queue, 
                            domain, target_field, visited_lock, queue_lock, 
                            browser_lock, current_context, saved_count_lock, 
                            saved_pbar, queue_pbar, saved_count, logger,
                            worker_id, playwright, user_data_dir, headless, separate_windows, browser_contexts
                        )
                        
                        # 컨텍스트나 페이지가 변경되었으면 업데이트
                        if updated_context != current_context:
                            current_context = updated_context
                            logger.info(f"워커 {worker_id}: 컨텍스트 업데이트됨")
                        
                        if new_page != page:
                            page = new_page
                            logger.info(f"워커 {worker_id}: 페이지 업데이트됨")
                        
                        # saved_count는 process_single_page에서 처리됨
                                
                finally:
                    # 활성 워커 수 감소 및 활동 시간 업데이트
                    async with active_workers_lock:
                        active_workers -= 1
                    async with activity_lock:
                        last_activity_time = asyncio.get_event_loop().time()
                    
        except Exception as e:
            logger.error(f"워커 {worker_id} 오류: {e}")
        finally:
            logger.info(f"워커 {worker_id} 종료")
            await page.close()

    async def timeout_monitor():
        """30초 동안 모든 워커가 idle이면 종료 신호"""
        nonlocal active_workers, last_activity_time
        
        while not shutdown_event.is_set():
            await asyncio.sleep(5)  # 5초마다 체크
            
            current_time = asyncio.get_event_loop().time()
            
            async with active_workers_lock:
                current_active = active_workers
            
            async with activity_lock:
                time_since_last_activity = current_time - last_activity_time
            
            if current_active == 0 and time_since_last_activity >= IDLE_TIMEOUT:
                logger.info(f"타임아웃: {IDLE_TIMEOUT}초 동안 모든 워커가 idle 상태 - 종료 신호 발송")
                shutdown_event.set()
                break

    async def progress_monitor():
        """Progress bar 상태 업데이트"""
        while not shutdown_event.is_set():
            await asyncio.sleep(1)  # 1초마다 업데이트
            
            # 현재 상태 정보 수집
            async with visited_lock:
                visited_count = len(visited)
            async with queue_lock:
                queue_count = len(queue)
            async with saved_count_lock:
                current_saved = len(saved_count)
            async with active_workers_lock:
                current_active = active_workers
                
            # Progress bar 설명 업데이트
            visited_pbar.set_description(f"📋 Visited ({visited_count})")
            queue_pbar.set_description(f"📝 Queue ({queue_count}) [Active: {current_active}]")
            saved_pbar.set_description(f"💾 Saved ({current_saved})")
            
            visited_pbar.refresh()
            queue_pbar.refresh()
            saved_pbar.refresh()

    try:
        logger.info("크롤링 워커들 시작")
        
        # 워커 태스크들 생성
        if separate_windows:
            workers = [asyncio.create_task(worker(i)) for i in range(max_concurrent)]
        else:
            workers = [asyncio.create_task(worker(i)) for i in range(max_concurrent)]
        
        # 모니터링 태스크들 추가
        timeout_task = asyncio.create_task(timeout_monitor())
        progress_task = asyncio.create_task(progress_monitor())
        
        # 모든 태스크가 완료될 때까지 대기
        await asyncio.gather(*workers, timeout_task, progress_task)

    finally:
        # Progress bars 정리
        visited_pbar.close()
        queue_pbar.close()
        saved_pbar.close()
        
        if separate_windows:
            for context in browser_contexts:
                await context.close()
        else:
            await browser_context.close()
        await playwright.stop()
    
    logger.info(f"크롤링 완료 - {out_path} 에 {len(visited)}개 페이지 처리됨, {len(saved_count)}개 파일 저장됨")
    
    # Progress bars가 닫힌 후에만 화면에 최종 결과 출력
    print(f"✅ 크롤링 완료! 로그: {log_file}")
    print(f"📁 저장 경로: {out_path}")
    print(f"📊 처리 결과: {len(visited)}개 페이지 방문, {len(saved_count)}개 파일 저장")


def setup_logger(log_file: Path) -> logging.Logger:
    """로거 설정"""
    logger = logging.getLogger('uptodate_crawler')
    logger.setLevel(logging.INFO)
    
    # 기존 핸들러 제거
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 파일 핸들러 추가
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 포맷터 설정
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    return logger


if __name__ == "__main__":
    # 캐시 초기화가 필요하면 clear_cache=True로 설정
    asyncio.run(crawl_uptodate_streaming(
        Path("data/uptodate/general-surgery"),  # 폴더 경로로 변경
        base_url="https://www.uptodate.com/contents/table-of-contents",
        target_field="general-surgery",
        domain="www.uptodate.com",
        headless=True,
        clear_cache=False,  # 캐시 문제 시 True로 변경
        max_concurrent=5,  # 동시 처리할 페이지 수 (3-5개 권장)
        separate_windows=True  # 3개의 별도 창이 열림
    ))
