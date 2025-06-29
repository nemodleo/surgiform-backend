"""
의료 문서용 RAG 검색 엔진  
그래프와 벡터 검색을 결합한 의료 문서 검색 시스템
"""

import re
from typing import List, Dict, Any
from langchain_community.vectorstores import Neo4jVector

from surgiform.core.ingest.uptodate.medical_graph_builder import MedicalGraphRAGBuilder


class MedicalRAGQueryEngine:
    """의료 RAG 쿼리 엔진"""
    
    def __init__(self, graph_builder: MedicalGraphRAGBuilder):
        self.builder = graph_builder
    
    def query(self, query: str, k_vector: int = 5, k_graph: int = 10) -> Dict[str, Any]:
        """통합 쿼리 실행"""
        print(f"🔍 Executing query: {query}")
        
        # 1. 벡터 검색
        vector_results = self.builder.query_similar_sentences(query, k=k_vector)
        
        # 2. 그래프 검색
        graph_results = self.builder.query_graph_context(query, limit=k_graph)
        
        # 3. 결과 통합
        clean_query = re.sub(r'\[\d+(?:,\d+)*\]', '', query.lower()).strip()
        
        combined_results = {
            "query_info": {
                "original_query": query,
                "cleaned_query": clean_query,
                "vector_results_count": len(vector_results),
                "graph_results_count": len(graph_results)
            },
            "vector_results": vector_results,
            "graph_results": graph_results,
            "combined_sentences": self._combine_and_deduplicate(vector_results, graph_results)
        }
        
        print(f"📊 Found {len(vector_results)} vector results, {len(graph_results)} graph results")
        
        return combined_results
    
    def _combine_and_deduplicate(self, vector_results: List[Dict], graph_results: List[Dict]) -> List[Dict]:
        """벡터와 그래프 결과를 결합하고 중복 제거"""
        seen_sentences = set()
        combined = []
        
        # 벡터 결과 추가
        for result in vector_results:
            text = result["text"]
            if text not in seen_sentences:
                seen_sentences.add(text)
                combined.append({
                    "text": text,
                    "source": "vector",
                    "metadata": result.get("metadata", {}),
                    "section": result.get("metadata", {}).get("section", "Unknown"),
                    "entities": [],
                    "references": [],
                    "images": [],
                    "tables": []
                })
        
        # 그래프 결과 추가
        for result in graph_results:
            text = result["sentence"]
            if text not in seen_sentences:
                seen_sentences.add(text)
                combined.append({
                    "text": text,
                    "source": "graph",
                    "section": result.get("section", "Unknown"),
                    "entities": result.get("entities", []),
                    "references": [ref for ref in result.get("references", []) if ref.get("text") or ref.get("id")],
                    "images": [img for img in result.get("images", []) if img.get("url")],
                    "tables": [tbl for tbl in result.get("tables", []) if tbl.get("url")]
                })
        
        return combined
    
    def query_by_entity(self, entity_name: str, entity_type: str = None) -> List[Dict]:
        """특정 의료 엔티티로 검색"""
        query = """
        MATCH (entity:MedicalEntity)-[:MENTIONS]-(sent:Sentence)
        WHERE toLower(entity.name) CONTAINS toLower($entity_name)
        """
        
        params = {"entity_name": entity_name}
        
        if entity_type:
            query += " AND entity.type = $entity_type"
            params["entity_type"] = entity_type
        
        query += """
        OPTIONAL MATCH (sec:Section)-[:HAS_SENTENCE]->(sent)
        OPTIONAL MATCH (sent)-[:CITES]->(ref:Reference)
        OPTIONAL MATCH (sent)-[:REFERENCES_IMAGE]->(img:Image)
        
        RETURN sent.text as sentence,
               sent.id as sentence_id,
               sec.title as section,
               entity.name as entity_name,
               entity.type as entity_type,
               collect(DISTINCT {text: ref.text, url: ref.url}) as references,
               collect(DISTINCT {url: img.url, description: img.description}) as images
        LIMIT 20
        """
        
        try:
            return self.builder.graph.query(query, params)
        except Exception as e:
            print(f"❌ Entity query error: {e}")
            return []
    
    def query_by_section(self, section_title: str) -> List[Dict]:
        """특정 섹션의 모든 문장 조회"""
        query = """
        MATCH (sec:Section)-[:HAS_SENTENCE]->(sent:Sentence)
        WHERE toLower(sec.title) CONTAINS toLower($section_title)
        
        OPTIONAL MATCH (sent)-[:MENTIONS]->(entity:MedicalEntity)
        OPTIONAL MATCH (sent)-[:CITES]->(ref:Reference)
        OPTIONAL MATCH (sent)-[:REFERENCES_IMAGE]->(img:Image)
        
        RETURN sent.text as sentence,
               sent.id as sentence_id,
               sec.title as section,
               collect(DISTINCT entity.name) as entities,
               collect(DISTINCT {text: ref.text, url: ref.url}) as references,
               collect(DISTINCT {url: img.url, description: img.description}) as images
        ORDER BY sent.created_at
        """
        
        try:
            return self.builder.graph.query(query, {"section_title": section_title})
        except Exception as e:
            print(f"❌ Section query error: {e}")
            return []
    
    def query_related_images(self, query: str, limit: int = 10) -> List[Dict]:
        """텍스트 쿼리로 관련 이미지 검색"""
        print(f"🖼️ 이미지 검색: {query}")
        
        clean_query = re.sub(r'\[\d+(?:,\d+)*\]', '', query.lower()).strip()
        query_words = [word.strip() for word in clean_query.split() if len(word.strip()) > 2]
        
        # 이미지 검색 전략들
        image_strategies = [
            # 전략 1: 문장 텍스트에서 키워드 매치하여 이미지 찾기
            """
            MATCH (sent:Sentence)-[:REFERENCES_IMAGE]->(img:Image)
            WHERE any(word IN $query_words WHERE toLower(sent.text) CONTAINS word)
            
            OPTIONAL MATCH (sent)-[:MENTIONS]->(entity:MedicalEntity)
            OPTIONAL MATCH (sec:Section)-[:HAS_SENTENCE]->(sent)
            
            WITH sent, img, sec, collect(DISTINCT entity.name) as entities
            
            RETURN sent.text as sentence,
                   sent.id as sentence_id,
                   COALESCE(sec.title, sent.section_name) as section,
                   img.url as image_url,
                   img.description as image_description,
                   entities
            ORDER BY sent.created_at DESC
            LIMIT $limit
            """,
            
            # 전략 2: 의료 엔티티를 통한 이미지 검색
            """
            MATCH (entity:MedicalEntity)-[:MENTIONS]-(sent:Sentence)-[:REFERENCES_IMAGE]->(img:Image)
            WHERE any(word IN $query_words WHERE toLower(entity.name) CONTAINS word)
            
            OPTIONAL MATCH (sec:Section)-[:HAS_SENTENCE]->(sent)
            OPTIONAL MATCH (sent)-[:MENTIONS]->(all_entities:MedicalEntity)
            
            WITH sent, img, sec, entity.name as first_entity, collect(DISTINCT all_entities.name) as entities
            
            RETURN sent.text as sentence,
                   sent.id as sentence_id,
                   COALESCE(sec.title, sent.section_name) as section,
                   img.url as image_url,
                   img.description as image_description,
                   entities
            ORDER BY first_entity
            LIMIT $limit
            """,
            
            # 전략 3: 전체 쿼리 텍스트로 이미지 검색
            """
            MATCH (sent:Sentence)-[:REFERENCES_IMAGE]->(img:Image)
            WHERE toLower(sent.text) CONTAINS $search_term
            
            OPTIONAL MATCH (sent)-[:MENTIONS]->(entity:MedicalEntity)
            OPTIONAL MATCH (sec:Section)-[:HAS_SENTENCE]->(sent)
            
            WITH sent, img, sec, collect(DISTINCT entity.name) as entities
            
            RETURN sent.text as sentence,
                   sent.id as sentence_id,
                   COALESCE(sec.title, sent.section_name) as section,
                   img.url as image_url,
                   img.description as image_description,
                   entities
            ORDER BY sent.created_at DESC
            LIMIT $limit
            """
        ]
        
        # 각 전략 시도
        for i, strategy in enumerate(image_strategies, 1):
            try:
                if i <= 2:  # 단어별 검색
                    params = {"query_words": query_words, "limit": limit}
                else:  # 전체 쿼리 검색
                    params = {"search_term": clean_query, "limit": limit}
                
                results = self.builder.graph.query(strategy, params)
                
                if results:
                    strategy_name = ["Text Match", "Entity Match", "Full Text"][i-1]
                    print(f"  ✅ 이미지 검색 전략 {i} ({strategy_name}) 성공: {len(results)}개 이미지")
                    return results
                    
            except Exception as e:
                strategy_name = ["Text Match", "Entity Match", "Full Text"][i-1]
                print(f"  ⚠️ 이미지 검색 전략 {i} ({strategy_name}) 실패: {e}")
                continue
        
        print(f"  ❌ 모든 이미지 검색 전략 실패")
        return []
    
    def query_images_by_keywords(self, keywords: List[str], limit: int = 5) -> List[Dict]:
        """특정 키워드들로 이미지 검색"""
        print(f"🔍 키워드 이미지 검색: {keywords}")
        
        keyword_query = """
        MATCH (sent:Sentence)-[:REFERENCES_IMAGE]->(img:Image)
        WHERE any(keyword IN $keywords WHERE toLower(sent.text) CONTAINS toLower(keyword))
        
        OPTIONAL MATCH (sent)-[:MENTIONS]->(entity:MedicalEntity)
        OPTIONAL MATCH (sec:Section)-[:HAS_SENTENCE]->(sent)
        
        WITH sent, img, sec, collect(DISTINCT entity.name) as entities
        
        RETURN sent.text as sentence,
               sent.id as sentence_id,
               COALESCE(sec.title, sent.section_name) as section,
               img.url as image_url,
               img.description as image_description,
               entities
        ORDER BY sent.created_at DESC
        LIMIT $limit
        """
        
        try:
            results = self.builder.graph.query(keyword_query, {"keywords": keywords, "limit": limit})
            print(f"  ✅ 키워드 검색 성공: {len(results)}개 이미지")
            return results
        except Exception as e:
            print(f"  ❌ 키워드 이미지 검색 실패: {e}")
            return []
    
    def query_related_tables(self, query: str, limit: int = 10) -> List[Dict]:
        """텍스트 쿼리로 관련 테이블 검색"""
        print(f"📊 테이블 검색: {query}")
        
        clean_query = re.sub(r'\[\d+(?:,\d+)*\]', '', query.lower()).strip()
        query_words = [word.strip() for word in clean_query.split() if len(word.strip()) > 2]
        
        # 테이블 검색 전략들
        table_strategies = [
            # 전략 1: 문장 텍스트에서 키워드 매치하여 테이블 찾기
            """
            MATCH (sent:Sentence)-[:REFERENCES_TABLE]->(tbl:Table)
            WHERE any(word IN $query_words WHERE toLower(sent.text) CONTAINS word)
            
            OPTIONAL MATCH (sent)-[:MENTIONS]->(entity:MedicalEntity)
            OPTIONAL MATCH (sec:Section)-[:HAS_SENTENCE]->(sent)
            
            WITH sent, tbl, sec, collect(DISTINCT entity.name) as entities
            
            RETURN sent.text as sentence,
                   sent.id as sentence_id,
                   COALESCE(sec.title, sent.section_name) as section,
                   tbl.id as table_id,
                   tbl.url as table_url,
                   tbl.title as table_title,
                   tbl.type as table_type,
                   entities
            ORDER BY sent.created_at DESC
            LIMIT $limit
            """,
            
            # 전략 2: 의료 엔티티를 통한 테이블 검색
            """
            MATCH (entity:MedicalEntity)-[:MENTIONS]-(sent:Sentence)-[:REFERENCES_TABLE]->(tbl:Table)
            WHERE any(word IN $query_words WHERE toLower(entity.name) CONTAINS word)
            
            OPTIONAL MATCH (sec:Section)-[:HAS_SENTENCE]->(sent)
            OPTIONAL MATCH (sent)-[:MENTIONS]->(all_entities:MedicalEntity)
            
            WITH sent, tbl, sec, entity.name as first_entity, collect(DISTINCT all_entities.name) as entities
            
            RETURN sent.text as sentence,
                   sent.id as sentence_id,
                   COALESCE(sec.title, sent.section_name) as section,
                   tbl.id as table_id,
                   tbl.url as table_url,
                   tbl.title as table_title,
                   tbl.type as table_type,
                   entities
            ORDER BY first_entity
            LIMIT $limit
            """,
            
            # 전략 3: 테이블 제목에서 직접 검색
            """
            MATCH (tbl:Table)
            WHERE any(word IN $query_words WHERE toLower(tbl.title) CONTAINS word)
            
            OPTIONAL MATCH (sent:Sentence)-[:REFERENCES_TABLE]->(tbl)
            OPTIONAL MATCH (sent)-[:MENTIONS]->(entity:MedicalEntity)
            OPTIONAL MATCH (sec:Section)-[:HAS_SENTENCE]->(sent)
            
            WITH tbl, sent, sec, collect(DISTINCT entity.name) as entities
            
            RETURN COALESCE(sent.text, 'Table reference') as sentence,
                   COALESCE(sent.id, '') as sentence_id,
                   COALESCE(sec.title, sent.section_name, 'Unknown') as section,
                   tbl.id as table_id,
                   tbl.url as table_url,
                   tbl.title as table_title,
                   tbl.type as table_type,
                   entities
            ORDER BY tbl.title
            LIMIT $limit
            """
        ]
        
        # 각 전략 시도
        for i, strategy in enumerate(table_strategies, 1):
            try:
                params = {"query_words": query_words, "limit": limit}
                results = self.builder.graph.query(strategy, params)
                
                if results:
                    strategy_name = ["Text Match", "Entity Match", "Title Match"][i-1]
                    print(f"  ✅ 테이블 검색 전략 {i} ({strategy_name}) 성공: {len(results)}개 테이블")
                    return results
                    
            except Exception as e:
                strategy_name = ["Text Match", "Entity Match", "Title Match"][i-1]
                print(f"  ⚠️ 테이블 검색 전략 {i} ({strategy_name}) 실패: {e}")
                continue
        
        print(f"  ❌ 모든 테이블 검색 전략 실패")
        return []
    
    def query_tables_by_keywords(self, keywords: List[str], limit: int = 5) -> List[Dict]:
        """특정 키워드들로 테이블 검색"""
        print(f"🔍 키워드 테이블 검색: {keywords}")
        
        keyword_query = """
        MATCH (sent:Sentence)-[:REFERENCES_TABLE]->(tbl:Table)
        WHERE any(keyword IN $keywords WHERE toLower(sent.text) CONTAINS toLower(keyword) 
                                         OR toLower(tbl.title) CONTAINS toLower(keyword))
        
        OPTIONAL MATCH (sent)-[:MENTIONS]->(entity:MedicalEntity)
        OPTIONAL MATCH (sec:Section)-[:HAS_SENTENCE]->(sent)
        
        WITH sent, tbl, sec, collect(DISTINCT entity.name) as entities
        
        RETURN sent.text as sentence,
               sent.id as sentence_id,
               COALESCE(sec.title, sent.section_name) as section,
               tbl.id as table_id,
               tbl.url as table_url,
               tbl.title as table_title,
               tbl.type as table_type,
               entities
        ORDER BY sent.created_at DESC
        LIMIT $limit
        """
        
        try:
            results = self.builder.graph.query(keyword_query, {"keywords": keywords, "limit": limit})
            print(f"  ✅ 키워드 테이블 검색 성공: {len(results)}개 테이블")
            return results
        except Exception as e:
            print(f"  ❌ 키워드 테이블 검색 실패: {e}")
            return []
    
    def query_connected_resources(self, query: str, k_vector: int = 3, k_graph: int = 5) -> Dict[str, Any]:
        """선택된 문장에 연결된 리소스 방식 - 더 정확한 검색"""
        print(f"🔗 연결된 리소스 검색: {query}")
        
        # 1. 먼저 관련 문장들 선택
        text_results = self.query(query, k_vector=k_vector, k_graph=k_graph)
        
        if not text_results['combined_sentences']:
            print("  ⚠️ 관련 문장을 찾을 수 없습니다")
            return {
                "query_info": text_results["query_info"],
                "selected_sentences": [],
                "connected_images": [],
                "connected_tables": [],
                "connected_references": [],
                "total_connected_images": 0,
                "total_connected_tables": 0,
                "total_connected_references": 0
            }
        
        # 2. 선택된 문장들의 ID 수집 (개선된 로직)
        sentence_ids = []
        
        # 2-1. 그래프 검색 결과에서 sentence_id 수집
        for result in text_results['graph_results']:
            if result.get('sentence_id'):
                sentence_ids.append(result['sentence_id'])
        
        # 2-2. 벡터 검색 결과에서 sentence_id 수집 (metadata에서)
        for sentence in text_results['combined_sentences']:
            if sentence.get('metadata', {}).get('sentence_id'):
                sentence_ids.append(sentence['metadata']['sentence_id'])
        
        # 2-3. 중복 제거
        sentence_ids = list(set(sentence_ids))
        
        print(f"  📝 선택된 문장 {len(sentence_ids)}개에서 연결된 리소스 검색...")
        print(f"      문장 ID들: {sentence_ids[:3]}{'...' if len(sentence_ids) > 3 else ''}")
        
        # 3. 선택된 문장들에 연결된 이미지 찾기
        connected_images = []
        connected_tables = []  
        connected_references = []
        
        if sentence_ids:
            # 이미지 쿼리
            image_query = """
            MATCH (sent:Sentence)-[:REFERENCES_IMAGE]->(img:Image)
            WHERE sent.id IN $sentence_ids
            
            OPTIONAL MATCH (sec:Section)-[:HAS_SENTENCE]->(sent)
            OPTIONAL MATCH (sent)-[:MENTIONS]->(entity:MedicalEntity)
            
            WITH sent, img, sec, collect(DISTINCT entity.name) as entities
            
            RETURN sent.text as sentence,
                   sent.id as sentence_id,
                   COALESCE(sec.title, sent.section_name) as section,
                   img.url as image_url,
                   img.description as image_description,
                   img.id as image_id,
                   entities
            ORDER BY sentence_id
            """
            
            # 테이블 쿼리
            table_query = """
            MATCH (sent:Sentence)-[:REFERENCES_TABLE]->(tbl:Table)
            WHERE sent.id IN $sentence_ids
            
            OPTIONAL MATCH (sec:Section)-[:HAS_SENTENCE]->(sent)
            OPTIONAL MATCH (sent)-[:MENTIONS]->(entity:MedicalEntity)
            
            WITH sent, tbl, sec, collect(DISTINCT entity.name) as entities
            
            RETURN sent.text as sentence,
                   sent.id as sentence_id,
                   COALESCE(sec.title, sent.section_name) as section,
                   tbl.id as table_id,
                   tbl.url as table_url,
                   tbl.title as table_title,
                   tbl.type as table_type,
                   entities
            ORDER BY sentence_id
            """
            
            # 참조 쿼리
            reference_query = """
            MATCH (sent:Sentence)-[:CITES]->(ref:Reference)
            WHERE sent.id IN $sentence_ids
            
            OPTIONAL MATCH (sec:Section)-[:HAS_SENTENCE]->(sent)
            OPTIONAL MATCH (sent)-[:MENTIONS]->(entity:MedicalEntity)
            
            WITH sent, ref, sec, collect(DISTINCT entity.name) as entities
            
            RETURN sent.text as sentence,
                   sent.id as sentence_id,
                   COALESCE(sec.title, sent.section_name) as section,
                   ref.id as reference_id,
                   ref.text as reference_text,
                   ref.url as reference_url,
                   ref.type as reference_type,
                   entities
            ORDER BY sentence_id
            """
            
            try:
                # 이미지 검색 실행
                img_results = self.builder.graph.query(image_query, {"sentence_ids": sentence_ids})
                connected_images = img_results
                print(f"    🖼️ 연결된 이미지: {len(connected_images)}개")
                
                # 테이블 검색 실행  
                tbl_results = self.builder.graph.query(table_query, {"sentence_ids": sentence_ids})
                connected_tables = tbl_results
                print(f"    📊 연결된 테이블: {len(connected_tables)}개")
                
                # 참조 검색 실행
                ref_results = self.builder.graph.query(reference_query, {"sentence_ids": sentence_ids})
                connected_references = ref_results
                print(f"    📚 연결된 참조: {len(connected_references)}개")
                
            except Exception as e:
                print(f"    ❌ 연결된 리소스 검색 오류: {e}")
        
        # 4. 결과 통합
        result = {
            "query_info": text_results["query_info"],
            "selected_sentences": text_results['combined_sentences'],
            "connected_images": connected_images,
            "connected_tables": connected_tables,
            "connected_references": connected_references,
            "total_connected_images": len(connected_images),
            "total_connected_tables": len(connected_tables),
            "total_connected_references": len(connected_references),
            "debug_sentence_ids": sentence_ids  # 디버깅용
        }
        
        print(f"📊 연결된 리소스 결과: 문장 {len(text_results['combined_sentences'])}개 → 이미지 {len(connected_images)}개, 테이블 {len(connected_tables)}개, 참조 {len(connected_references)}개")
        
        return result

    def query_all_elements(self, query: str, k_vector: int = 3, k_graph: int = 5, k_images: int = 3, k_tables: int = 3) -> Dict[str, Any]:
        """텍스트 + 이미지 + 테이블 완전 통합 검색"""
        print(f"🔍 완전 통합 검색 (텍스트 + 이미지 + 테이블): {query}")
        
        # 1. 기본 텍스트 검색
        text_results = self.query(query, k_vector=k_vector, k_graph=k_graph)
        
        # 2. 이미지 검색
        image_results = self.query_related_images(query, limit=k_images)
        
        # 3. 테이블 검색
        table_results = self.query_related_tables(query, limit=k_tables)
        
        # 4. 결과 통합
        combined_results = text_results.copy()
        combined_results["image_results"] = image_results
        combined_results["table_results"] = table_results
        combined_results["total_images_found"] = len(image_results)
        combined_results["total_tables_found"] = len(table_results)
        
        # 5. 요약 정보 추가
        if image_results:
            image_summary = []
            for img_result in image_results:
                image_summary.append({
                    "image_url": img_result["image_url"],
                    "image_description": img_result["image_description"],
                    "context_sentence": img_result["sentence"][:100] + "...",
                    "section": img_result["section"],
                    "entities": img_result["entities"]
                })
            combined_results["image_summary"] = image_summary
        
        if table_results:
            table_summary = []
            for tbl_result in table_results:
                table_summary.append({
                    "table_id": tbl_result["table_id"],
                    "table_url": tbl_result["table_url"],
                    "table_title": tbl_result["table_title"],
                    "context_sentence": tbl_result["sentence"][:100] + "..." if tbl_result["sentence"] else "",
                    "section": tbl_result["section"],
                    "entities": tbl_result["entities"]
                })
            combined_results["table_summary"] = table_summary
        
        print(f"📊 완전 통합 결과: 텍스트 {len(text_results['combined_sentences'])}개, 이미지 {len(image_results)}개, 테이블 {len(table_results)}개")
        
        return combined_results

# # 편의 함수들
# def build_medical_rag_from_file(file_path: str) -> tuple:
#     """파일로부터 의료 RAG 시스템 구축"""
#     from medical_parser import parse_uptodate_file, extract_document_info, load_uptodate_document
    
#     print(f"🚀 Building Medical RAG from file: {file_path}")
    
#     # 1. 문서 파싱
#     parser = parse_uptodate_file(file_path)
    
#     # 2. 문서 정보 추출
#     html_content = load_uptodate_document(file_path)
#     title, url = extract_document_info(html_content)
    
#     # 3. RAG 시스템 구축
#     builder = MedicalGraphRAGBuilder()
#     builder.build_graph_from_parser(parser, title, url)
    
#     # 4. 쿼리 엔진 생성
#     query_engine = MedicalRAGQueryEngine(builder)
    
#     print(f"✅ Medical RAG system ready!")
    
#     return builder, query_engine
