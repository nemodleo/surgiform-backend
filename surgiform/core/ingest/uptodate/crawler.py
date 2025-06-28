import asyncio
import os
import dotenv
import json
import re
from pathlib import Path
from typing import Set
from urllib.parse import urlparse
from urllib.parse import urlunparse
from urllib.parse import ParseResult
from playwright.async_api import async_playwright

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
    browser_context
) -> None:
    """단일 페이지 처리 워커 함수"""
    try:
        print(f"🌐 {url}")
        await page.goto(url, wait_until="networkidle", timeout=60_000)
        
        # 페이지 로드 후 검색 페이지로 리다이렉트 되었는지 확인
        current_url = page.url
        if "/contents/search" in current_url or "/login" in current_url:
            print("🔄 검색 페이지로 리다이렉트 감지됨. 페이지를 재생성합니다...")
            async with browser_lock:
                await page.close()
                page = await browser_context.new_page()
            
            # 원래 URL로 다시 이동
            await page.goto(url, wait_until="networkidle", timeout=60_000)
            
    except Exception as e:
        print(f"⚠️ load failed: {e}")
        return

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
            print(f"    ⏭️ 이미 존재함: {filename}")
            return  # 파일이 이미 존재하면 스킵
        
        print(f"    ✅ {url}")
        try:
            content = await page.locator("#topicContent").inner_html()
        except Exception as e:
            print(f"    ⚠️ 콘텐츠 추출 실패: {e}")
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
            print(f"    💾 저장됨: {filename}")
        except Exception as e:
            print(f"    ❌ 저장 실패: {e}")
        
        return  # 본문 페이지는 링크를 더 탐색하지 않음

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
                
    except Exception as e:
        print(f"    ⚠️ 링크 수집 실패: {e}")


async def crawl_uptodate_streaming(
        out_path: Path,
        base_url: str = "https://www.uptodate.com/contents/table-of-contents/",
        target_field: str | None = None,
        domain: str = "www.uptodate.com",
        headless: bool = True,
        clear_cache: bool = False,
        max_concurrent: int = 5  # 동시 처리할 페이지 수
):
    _url = f"{base_url}/{target_field}" if target_field else base_url
    visited: Set[str] = set()
    queue: list[str] = [_url]
    
    # 동시성 제어를 위한 락과 세마포어
    visited_lock = asyncio.Lock()
    queue_lock = asyncio.Lock()
    browser_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(max_concurrent)

    # out_path를 디렉토리로 처리
    out_path.mkdir(parents=True, exist_ok=True)

    playwright = await async_playwright().start()
    
    # 💾 user_data_dir에 프로필을 저장합니다
    user_data_dir = "./uptodate_user_profile"
    
    # 캐시 초기화 요청이 있으면 프로필 디렉토리 삭제
    profile_path = Path(user_data_dir)
    if clear_cache and profile_path.exists():
        import shutil
        print(f"🗑️ 캐시 초기화: {user_data_dir} 삭제 중...")
        shutil.rmtree(profile_path)
        print("✅ 캐시가 초기화되었습니다.")
    
    # 프로필 디렉토리 상태 확인
    if profile_path.exists():
        print(f"💾 기존 프로필 디렉토리 발견: {user_data_dir}")
        # 프로필 내용 확인
        profile_files = list(profile_path.glob("*"))
        print(f"   프로필 파일 개수: {len(profile_files)}")
    else:
        print(f"🆕 새로운 프로필 디렉토리 생성 예정: {user_data_dir}")
    
    print(f"🚀 브라우저 시작 중... (headless: {headless}, 동시처리: {max_concurrent})")
    browser_context = await playwright.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        headless=headless
    )

    async def worker():
        """워커 함수: 큐에서 URL을 가져와서 처리"""
        page = await browser_context.new_page()
        
        try:
            while True:
                # 큐에서 URL 가져오기
                async with queue_lock:
                    if not queue:
                        break
                    url = strip_fragment(queue.pop(0))
                
                # 방문 체크
                async with visited_lock:
                    if url in visited:
                        continue
                    visited.add(url)
                
                # 세마포어로 동시 처리 수 제한
                async with semaphore:
                    await process_single_page(
                        page, url, out_path, visited, queue, 
                        domain, target_field, visited_lock, queue_lock, 
                        browser_lock, browser_context
                    )
                    
        finally:
            await page.close()

    try:
        print(f"🚀 크롤링 시작: {_url}")
        
        # 워커 태스크들 생성
        workers = [asyncio.create_task(worker()) for _ in range(max_concurrent)]
        
        # 모든 워커가 완료될 때까지 대기
        await asyncio.gather(*workers)

    finally:
        await browser_context.close()
        await playwright.stop()
    
    print(f"✅ 크롤링 완료 – {out_path} 에 {len(visited)}개 페이지 처리됨")


if __name__ == "__main__":
    # 캐시 초기화가 필요하면 clear_cache=True로 설정
    asyncio.run(crawl_uptodate_streaming(
        Path("data/uptodate/general-surgery"),  # 폴더 경로로 변경
        base_url="https://www.uptodate.com/contents/table-of-contents",
        target_field="general-surgery",
        domain="www.uptodate.com",
        headless=False,
        clear_cache=False,  # 캐시 문제 시 True로 변경
        max_concurrent=3  # 동시 처리할 페이지 수 (3-5개 권장)
    ))
