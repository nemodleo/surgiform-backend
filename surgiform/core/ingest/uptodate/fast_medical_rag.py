"""
초고속 Elasticsearch 의료 RAG 시스템
- 임베딩 선택적 생성 (기본 OFF)  
- 병렬 처리
- 배치 최적화
- 간소화된 인덱싱
"""

import json
import os
import sys
import glob
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch.helpers import parallel_bulk
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

# 필요한 모듈 임포트
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from surgiform.core.ingest.uptodate.medical_parser import MedicalDocumentParser
from surgiform.external.es_client import get_es_client
from surgiform.external.openai_client import get_openai_client


class UltraFastMedicalRAG:
    """초고속 의료 RAG 시스템"""
    
    def __init__(self, enable_embeddings=False):
        print("🚀 ULTRA FAST Medical RAG System")
        
        # Elasticsearch
        self.es_client = get_es_client()
        print("✅ Elasticsearch connected")
        
        # OpenAI (선택적)
        self.enable_embeddings = enable_embeddings
        if enable_embeddings:
            try:
                self.openai_client = get_openai_client()
                print("✅ Embeddings ENABLED")
            except:
                self.openai_client = None
                self.enable_embeddings = False
                print("⚠️ Embeddings DISABLED")
        else:
            self.openai_client = None
            print("⚡ Embeddings OFF (MAX SPEED)")
        
        # 인덱스
        self.indices = {
            "documents": "fast-docs",
            "sentences": "fast-sentences"
        }
        
        # 최적화 설정
        self.batch_size = 3000
        
    def create_indices(self):
        """최적화된 인덱스 생성"""
        print("🏗️ Creating fast indices...")
        
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "refresh_interval": "60s"
        }
        
        # 문서 인덱스
        doc_mapping = {
            "mappings": {
                "properties": {
                    "url": {"type": "keyword"},
                    "title": {"type": "text"},
                    "sentence_count": {"type": "short"},
                    "created_at": {"type": "date"}
                }
            },
            "settings": settings
        }
        
        # 문장 인덱스
        sentence_props = {
            "sentence_id": {"type": "keyword"},
            "document_url": {"type": "keyword"},
            "text": {"type": "text"},
            "document_title": {"type": "text"},
            "section": {"type": "keyword"},
            "entities": {"type": "keyword"},
            "created_at": {"type": "date"}
        }
        
        if self.enable_embeddings:
            sentence_props["embedding"] = {
                "type": "dense_vector",
                "dims": 1536,
                "similarity": "cosine"
            }
        
        sentence_mapping = {
            "mappings": {"properties": sentence_props},
            "settings": settings
        }
        
        # 인덱스 생성
        for name, mapping in [("documents", doc_mapping), ("sentences", sentence_mapping)]:
            index_name = self.indices[name]
            if not self.es_client.indices.exists(index=index_name):
                self.es_client.indices.create(
                    index=index_name,
                    mappings=mapping["mappings"],
                    settings=mapping["settings"]
                )
                print(f"  ✅ Created {index_name}")
            else:
                print(f"  ⚡ {index_name} exists")
    
    def get_embeddings(self, texts):
        """배치 임베딩 생성"""
        if not self.enable_embeddings:
            return [None] * len(texts)
        
        try:
            # 텍스트 길이 제한
            clean_texts = [t[:6000] if len(t) > 6000 else t for t in texts]
            
            response = self.openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=clean_texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            print(f"❌ Embedding failed: {e}")
            return [None] * len(texts)
    
    def index_document_ultra_fast(self, json_file):
        """초고속 문서 인덱싱"""
        try:
            # JSON 로드
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            title = data.get('title', 'Unknown')
            url = data.get('url', f'file://{json_file}')
            content = data.get('content', '')
            
            # 파싱
            parser = MedicalDocumentParser(url)
            parser.parse_html(content)
            
            if not parser.sentences:
                return False
            
            # 액션 준비
            actions = []
            
            # 1. 문서 메타데이터
            clean_title = title.replace(' - UpToDate', '').strip()
            actions.append({
                "_index": self.indices["documents"],
                "_id": url,
                "_source": {
                    "url": url,
                    "title": clean_title,
                    "sentence_count": len(parser.sentences),
                    "created_at": datetime.now().isoformat()
                }
            })
            
            # 2. 문장 데이터
            texts = [clean_title]  # 제목 먼저
            sentence_data = []
            
            # 제목 문장
            title_id = f"title_{hashlib.md5(url.encode()).hexdigest()[:8]}"
            sentence_data.append({
                "sentence_id": title_id,
                "document_url": url,
                "text": clean_title,
                "document_title": clean_title,
                "section": "TITLE",
                "entities": self.extract_simple_entities(clean_title),
                "created_at": datetime.now().isoformat()
            })
            
            # 일반 문장 (최대 150개)
            for sentence in parser.sentences[:150]:
                texts.append(sentence.text)
                sentence_data.append({
                    "sentence_id": sentence.sentence_id,
                    "document_url": url,
                    "text": sentence.text,
                    "document_title": clean_title,
                    "section": sentence.section[:20] if sentence.section else "",
                    "entities": sentence.medical_entities[:3],
                    "created_at": datetime.now().isoformat()
                })
            
            # 3. 임베딩 (선택적)
            embeddings = self.get_embeddings(texts)
            
            # 4. 문장 액션 생성
            for data, embedding in zip(sentence_data, embeddings):
                if embedding:
                    data["embedding"] = embedding
                
                actions.append({
                    "_index": self.indices["sentences"],
                    "_id": data["sentence_id"],
                    "_source": data
                })
            
            # 5. 배치 인덱싱
            success_count = 0
            for success, info in parallel_bulk(
                self.es_client, actions, 
                chunk_size=self.batch_size,
                thread_count=2
            ):
                if success:
                    success_count += 1
            
            return success_count > 0
            
        except Exception as e:
            print(f"❌ Error indexing {Path(json_file).name}: {e}")
            return False
    
    def extract_simple_entities(self, text):
        """간단한 엔티티 추출"""
        keywords = ['surgery', 'treatment', 'cancer', 'diagnosis', 'therapy']
        entities = []
        text_lower = text.lower()
        
        for keyword in keywords:
            if keyword in text_lower:
                entities.append(keyword)
        
        return entities[:3]
    
    def batch_index_ultra_fast(self, directory, max_files=None, workers=8):
        """초고속 배치 처리"""
        print(f"🚀 ULTRA FAST batch processing")
        print(f"⚡ Workers: {workers}, Embeddings: {'ON' if self.enable_embeddings else 'OFF'}")
        
        # 파일 찾기
        json_files = glob.glob(os.path.join(directory, "*.json"))
        if max_files:
            json_files = json_files[:max_files]
        
        print(f"📂 Found {len(json_files)} files")
        
        # 인덱스 생성
        self.create_indices()
        
        # 통계
        successful = []
        failed = []
        start_time = time.time()
        
        # 병렬 처리
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_file = {
                executor.submit(self.index_document_ultra_fast, f): f 
                for f in json_files
            }
            
            # 진행률 표시
            with tqdm(total=len(json_files), desc="⚡ ULTRA", unit="docs") as pbar:
                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    
                    try:
                        success = future.result(timeout=20)
                        if success:
                            successful.append(file_path)
                        else:
                            failed.append(file_path)
                    except Exception as e:
                        failed.append(file_path)
                    
                    # 실시간 속도 계산
                    elapsed = time.time() - start_time
                    speed = len(successful) / elapsed if elapsed > 0 else 0
                    
                    pbar.update(1)
                    pbar.set_postfix(speed=f"{speed:.1f}/s")
        
        # 최종 결과
        total_time = time.time() - start_time
        final_speed = len(successful) / total_time if total_time > 0 else 0
        
        print(f"\n🎉 COMPLETED!")
        print(f"⚡ SPEED: {final_speed:.2f} documents/second") 
        print(f"✅ Success: {len(successful)}/{len(json_files)}")
        print(f"⏱️ Time: {total_time:.1f}s")
        
        # 인덱스 새로고침
        for index in self.indices.values():
            self.es_client.indices.refresh(index=index)
        
        return {
            "success": len(successful),
            "failed": len(failed), 
            "speed": final_speed,
            "time": total_time
        }
    
    def search_fast(self, query, k=10):
        """초고속 검색"""
        start_time = time.time()
        
        try:
            response = self.es_client.search(
                index=self.indices["sentences"],
                query={
                    "multi_match": {
                        "query": query,
                        "fields": ["text^2", "document_title", "entities"]
                    }
                },
                _source=["text", "document_title", "section", "entities"],
                size=k
            )
            
            results = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                results.append({
                    "text": source.get("text", ""),
                    "title": source.get("document_title", ""),
                    "section": source.get("section", ""),
                    "entities": source.get("entities", []),
                    "score": hit['_score']
                })
            
            search_time = time.time() - start_time
            
            return {
                "query": query,
                "results": results,
                "count": len(results),
                "time": search_time
            }
            
        except Exception as e:
            return {
                "query": query,
                "results": [],
                "error": str(e),
                "time": time.time() - start_time
            }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='초고속 의료 RAG')
    parser.add_argument('--directory', default="data/uptodate/general-surgery")
    parser.add_argument('--max-files', type=int)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--embeddings', action='store_true')
    parser.add_argument('--search', action='store_true')
    
    args = parser.parse_args()
    
    try:
        # RAG 시스템
        rag = UltraFastMedicalRAG(enable_embeddings=args.embeddings)
        
        # 배치 처리
        result = rag.batch_index_ultra_fast(
            args.directory,
            max_files=args.max_files,
            workers=args.workers
        )
        
        print(f"\n🎯 FINAL SPEED: {result['speed']:.2f} docs/sec")
        
        # 검색 테스트
        if args.search:
            print("\n🔍 Search test:")
            for query in ["cancer", "surgery", "treatment"]:
                res = rag.search_fast(query, k=3)
                print(f"  {query}: {res['count']} results in {res['time']:.3f}s")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
