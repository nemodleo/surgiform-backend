"""
의료 문서용 Graph RAG 시스템 - 편의 함수들과 메인 스크립트
Graph RAG 구축과 검색을 위한 고수준 인터페이스
"""

import json
import os
import sys
import glob
from pathlib import Path
from typing import Dict

from surgiform.core.ingest.uptodate.medical_graph_builder import MedicalGraphRAGBuilder
from surgiform.core.ingest.uptodate.medical_rag_engine import MedicalRAGQueryEngine


def load_uptodate_json(file_path: str) -> Dict[str, str]:
    """UpToDate JSON 파일 로드"""
    print(f"📂 Loading JSON file: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    html_content = data.get('content')
    title = data.get('title')
    url = data.get('url')
    
    print(f"✅ Loaded: {title}")
    
    return {
        'html_content': html_content,
        'title': title, 
        'url': url
    }

def build_medical_rag_from_html(html_content: str, title: str, url: str) -> tuple:
    """HTML 내용으로부터 의료 RAG 시스템 구축"""
    print(f"🚀 Building Medical RAG from HTML: {title}")
    
    # RAG 시스템 구축
    builder = MedicalGraphRAGBuilder()
    builder.build_graph_from_html(html_content, title, url)
    
    # 쿼리 엔진 생성
    query_engine = MedicalRAGQueryEngine(builder)
    
    print(f"✅ Medical RAG system ready!")
    
    return builder, query_engine

def build_medical_rag_from_json(json_file_path: str) -> tuple:
    """JSON 파일로부터 의료 RAG 시스템 구축"""
    # JSON 파일 로드
    data = load_uptodate_json(json_file_path)
    
    # RAG 시스템 구축
    return build_medical_rag_from_html(
        data['html_content'], 
        data['title'], 
        data['url']
    )

def build_medical_rag_from_directory(directory_path: str = "data/uptodate/general-surgery", max_files: int = None) -> tuple:
    """디렉토리의 모든 JSON 파일들로부터 의료 RAG 시스템 구축"""
    import glob
    import os
    import sys
    from pathlib import Path
    from tqdm import tqdm
    from contextlib import redirect_stdout, redirect_stderr
    from io import StringIO
    
    # 로그 파일 경로 설정
    log_dir = Path(directory_path).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "medical_rag_build.log"
    
    print(f"🚀 Building Medical RAG from directory: {directory_path}")
    print(f"📝 Build logs will be saved to: {log_file}")
    
    # 디렉토리 절대 경로 생성
    if not os.path.isabs(directory_path):
        directory_path = os.path.join(os.getcwd(), directory_path)
    
    # JSON 파일들 찾기
    json_pattern = os.path.join(directory_path, "*.json")
    all_json_files = glob.glob(json_pattern)
    
    if not all_json_files:
        raise FileNotFoundError(f"No JSON files found in directory: {directory_path}")
    
    # 파일 수 제한 적용
    if max_files and max_files > 0:
        json_files = all_json_files[:max_files]
        print(f"📂 Found {len(all_json_files)} JSON files, processing first {len(json_files)} files")
    else:
        json_files = all_json_files
        print(f"📂 Found {len(json_files)} JSON files to process")
        
        # 전체 파일 처리 시 확인 요청
        if len(json_files) > 100:
            print(f"⚠️ Processing {len(json_files)} files will take a long time!")
            print(f"💡 Consider using --max-files option to limit the number of files")
    
    # 성공/실패 통계 및 변수 초기화
    successful_files = []
    failed_files = []
    builder = None
    query_engine = None
    rag_initialized = False
    
    try:
        # 진행률 표시를 위한 tqdm
        with tqdm(total=len(json_files), desc="🏥 Processing medical documents", 
                  bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]") as pbar:
            
            for i, json_file in enumerate(json_files):
                file_name = Path(json_file).name
                pbar.set_description(f"🏥 Processing: {file_name[:50]}...")
                
                # 로그를 파일과 버퍼로 리다이렉트
                with open(log_file, 'a', encoding='utf-8') as f:
                    with redirect_stdout(f), redirect_stderr(f):
                        f.write(f"\n{'='*80}\n")
                        f.write(f"Processing file {i+1}/{len(json_files)}: {file_name}\n")
                        f.write(f"{'='*80}\n")
                        
                        try:
                            if not rag_initialized:
                                # RAG 시스템 초기화 (첫 성공한 파일로)
                                f.write(f"🏗️ Initializing RAG system with: {file_name}\n")
                                builder, query_engine = build_medical_rag_from_json(json_file)
                                rag_initialized = True
                            else:
                                # JSON 파일 로드 및 추가
                                data = load_uptodate_json(json_file)
                                builder.build_graph_from_html(
                                    data['html_content'], 
                                    data['title'], 
                                    data['url']
                                )
                            
                            successful_files.append(json_file)
                            f.write(f"✅ Successfully processed: {file_name}\n")
                            
                        except Exception as e:
                            error_msg = f"❌ Failed to process {file_name}: {e}"
                            f.write(f"{error_msg}\n")
                            failed_files.append((json_file, str(e)))
                            # RAG가 초기화되지 않은 상태에서 실패한 경우 다음 파일로 계속 진행
                
                pbar.update(1)
                pbar.set_postfix(success=len(successful_files), failed=len(failed_files))
    
    finally:
        # 빌드 완료 후 모든 출력 복원
        print(f"\n🎉 Build completed!")
        
        # 최종 통계 출력
        print(f"\n📊 Processing Summary:")
        print(f"  ✅ Successfully processed: {len(successful_files)} files")
        print(f"  ❌ Failed: {len(failed_files)} files")
        
        if failed_files:
            print(f"\n⚠️ Failed files:")
            for failed_file, error in failed_files[:5]:  # 처음 5개만 표시
                print(f"    {Path(failed_file).name}: {error}")
            if len(failed_files) > 5:
                print(f"    ... and {len(failed_files) - 5} more (see log file)")
        
        # 전체 데이터베이스 통계
        if successful_files and builder is not None:
            total_stats = builder.get_document_stats()
            print(f"\n📈 Combined Database Statistics:")
            for key, value in total_stats.items():
                print(f"  {key}: {value}")
        
        print(f"\n📝 Detailed logs saved to: {log_file}")
        
        if builder is not None:
            print(f"✅ Multi-document RAG system ready with {len(successful_files)} documents!")
        else:
            print(f"❌ RAG system could not be initialized - all files failed to process")
    
    if not successful_files or builder is None:
        raise RuntimeError("No files were successfully processed or RAG system could not be initialized")
    
    return builder, query_engine

def get_directory_statistics(directory_path: str = "data/uptodate/general-surgery") -> Dict:
    """디렉토리의 JSON 파일들에 대한 통계 조회"""
    import glob
    import os
    from pathlib import Path
    
    # 디렉토리 절대 경로 생성
    if not os.path.isabs(directory_path):
        directory_path = os.path.join(os.getcwd(), directory_path)
    
    # JSON 파일들 찾기
    json_pattern = os.path.join(directory_path, "*.json")
    json_files = glob.glob(json_pattern)
    
    stats = {
        "directory_path": directory_path,
        "total_json_files": len(json_files),
        "file_sizes_mb": [],
        "sample_files": []
    }
    
    for json_file in json_files[:10]:  # 처음 10개 파일만 샘플링
        try:
            file_size = os.path.getsize(json_file) / (1024 * 1024)  # MB 단위
            stats["file_sizes_mb"].append(round(file_size, 2))
            
            # 파일명에서 제목 추출
            file_name = Path(json_file).stem
            stats["sample_files"].append(file_name)
            
        except Exception as e:
            continue
    
    if stats["file_sizes_mb"]:
        stats["avg_file_size_mb"] = round(sum(stats["file_sizes_mb"]) / len(stats["file_sizes_mb"]), 2)
        stats["total_size_mb"] = round(sum(stats["file_sizes_mb"]), 2)
    
    return stats

if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='의료 문서용 Graph RAG 시스템')
    
    # 디렉토리 모드와 단일 파일 모드 지원
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--directory', '-d', 
                      default="data/uptodate/general-surgery",
                      help='UpToDate JSON 파일들이 있는 디렉토리 경로 (기본값: data/uptodate/general-surgery)')
    group.add_argument('--json-file', '-f', 
                      help='단일 UpToDate JSON 파일 경로')
    
    parser.add_argument('--test-queries', action='store_true', help='테스트 쿼리 실행')
    parser.add_argument('--stats-only', action='store_true', help='디렉토리 통계만 조회')
    parser.add_argument('--max-files', type=int, help='처리할 최대 파일 수 (디렉토리 모드에서만 사용)')
    
    args = parser.parse_args()
    
    try:
        # 통계만 조회하는 경우
        if args.stats_only:
            directory_path = args.directory
            print(f"📊 Directory Statistics: {directory_path}")
            print("=" * 50)
            
            stats = get_directory_statistics(directory_path)
            print(f"📂 Total JSON files: {stats['total_json_files']}")
            
            if stats['file_sizes_mb']:
                print(f"📏 Average file size: {stats['avg_file_size_mb']} MB")
                print(f"💽 Total size: {stats['total_size_mb']} MB")
                
                print(f"\n📄 Sample files:")
                for i, file_name in enumerate(stats['sample_files'][:5], 1):
                    print(f"  {i}. {file_name}")
                
                if len(stats['sample_files']) < stats['total_json_files']:
                    remaining = stats['total_json_files'] - len(stats['sample_files'])
                    print(f"  ... 및 {remaining}개 파일 더")
            
            sys.exit(0)
        
        # RAG 시스템 구축
        if args.json_file:
            # 단일 파일 모드
            print(f"📄 Single file mode: {args.json_file}")
            builder, query_engine = build_medical_rag_from_json(args.json_file)
        else:
            # 디렉토리 모드 (기본값)
            print(f"📂 Directory mode: {args.directory}")
            if args.max_files:
                print(f"🔢 Limiting to {args.max_files} files")
            builder, query_engine = build_medical_rag_from_directory(args.directory, max_files=args.max_files)
        
        # 테스트 쿼리 실행 (옵션)
        if args.test_queries:
            # 의료 문서에 맞는 쿼리들
            test_queries = [
                "cancer treatment chemotherapy",
                "surgical complications management", 
                "metastases diagnosis imaging",
                "patient prognosis survival rate",
                "clinical trial evidence",
                "tumor resection procedure"
            ]
            
            print(f"\n🧪 Testing queries...")
            for query in test_queries:
                print(f"\n🔍 Query: {query}")
                        
                # 완전 통합 검색 테스트
                results = query_engine.query_all_elements(query, k_vector=2, k_graph=2, k_images=2, k_tables=2)
                
                vector_count = results['query_info']['vector_results_count']
                graph_count = results['query_info']['graph_results_count']
                images_count = results['total_images_found']
                tables_count = results['total_tables_found']
                print(f"📊 Results: {vector_count} vector + {graph_count} graph + {images_count} images + {tables_count} tables")
                
                # 상위 결과 출력
                if results['combined_sentences']:
                    top_result = results['combined_sentences'][0]
                    print(f"🎯 Top result: {top_result['text'][:100]}...")
                    print(f"   Section: {top_result['section']}")
                    print(f"   Source: {top_result['source']}")
                    if top_result['entities']:
                        print(f"   Entities: {', '.join(top_result['entities'][:3])}")
                    if top_result['references']:
                        print(f"   References: {len(top_result['references'])} found")
                    if top_result['images']:
                        print(f"   Images: {len(top_result['images'])} found")
                    if top_result['tables']:
                        print(f"   Tables: {len(top_result['tables'])} found")
        
        print(f"\n✅ RAG 시스템이 성공적으로 구축되었습니다!")
        print(f"\n💡 사용법:")
        
        if args.json_file:
            print(f"  # 단일 파일")
            print(f"  from medical_graph_rag import build_medical_rag_from_json")
            print(f"  builder, query_engine = build_medical_rag_from_json('{args.json_file}')")
        else:
            print(f"  # 디렉토리 전체")
            print(f"  from medical_graph_rag import build_medical_rag_from_directory")
            print(f"  builder, query_engine = build_medical_rag_from_directory('{args.directory}')")
            print(f"  results = query_engine.query('your medical question')")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
