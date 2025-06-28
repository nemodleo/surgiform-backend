"""
의료 문서용 Graph RAG 시스템
Neo4j 그래프 데이터베이스와 벡터 검색을 결합한 RAG 시스템
"""

import re
import json
import os
import hashlib
from typing import List, Dict, Any
from langchain_community.graphs import Neo4jGraph
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Neo4jVector
from dotenv import load_dotenv

from surgiform.core.ingest.uptodate.medical_parser import MedicalSentence, MedicalSection, MedicalDocumentParser

load_dotenv()

class MedicalGraphRAGBuilder:
    """의료 문서용 Graph RAG 구축기"""
    
    def __init__(self, neo4j_url: str = None, neo4j_username: str = None, 
                 neo4j_password: str = None, openai_api_key: str = None):
        """
        Graph RAG 시스템 초기화
        
        Args:
            neo4j_url: Neo4j 데이터베이스 URL
            neo4j_username: Neo4j 사용자명
            neo4j_password: Neo4j 비밀번호  
            openai_api_key: OpenAI API 키
        """
        # 환경변수에서 값 가져오기
        self.neo4j_url = neo4j_url or os.getenv('NEO4J_URL', 'bolt://localhost:7687')
        self.neo4j_username = neo4j_username or os.getenv('NEO4J_USERNAME', 'neo4j')
        self.neo4j_password = neo4j_password or os.getenv('NEO4J_PASSWORD', 'password')
        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        
        if not self.openai_api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        # Neo4j 연결
        print(f"🔗 Connecting to Neo4j at {self.neo4j_url}")
        self.graph = Neo4jGraph(
            url=self.neo4j_url,
            username=self.neo4j_username,
            password=self.neo4j_password
        )
        
        # OpenAI 임베딩 초기화
        print("🤖 Initializing OpenAI embeddings")
        self.embeddings = OpenAIEmbeddings(openai_api_key=self.openai_api_key)
        self.vector_store = None
        
        print("✅ MedicalGraphRAGBuilder initialized")
        
    def create_graph_schema(self):
        """그래프 스키마 생성 (Neo4j 5 호환)"""
        print("🏗️ Creating graph schema...")
        
        schema_queries = [
            # 노드 제약조건
            "CREATE CONSTRAINT sentence_id IF NOT EXISTS FOR (s:Sentence) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT section_id IF NOT EXISTS FOR (sec:Section) REQUIRE sec.id IS UNIQUE",
            "CREATE CONSTRAINT reference_id IF NOT EXISTS FOR (r:Reference) REQUIRE r.id IS UNIQUE", 
            "CREATE CONSTRAINT image_id IF NOT EXISTS FOR (i:Image) REQUIRE i.id IS UNIQUE",
            "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:MedicalEntity) REQUIRE e.name IS UNIQUE",
            "CREATE CONSTRAINT document_url IF NOT EXISTS FOR (d:Document) REQUIRE d.url IS UNIQUE",
            
            # 일반 인덱스
            "CREATE INDEX entity_name IF NOT EXISTS FOR (e:MedicalEntity) ON (e.name)",
            "CREATE INDEX entity_type IF NOT EXISTS FOR (e:MedicalEntity) ON (e.type)",
            "CREATE INDEX section_title IF NOT EXISTS FOR (sec:Section) ON (sec.title)",
        ]
        
        for query in schema_queries:
            try:
                self.graph.query(query)
                print(f"  ✅ {query}")
            except Exception as e:
                print(f"  ⚠️ Schema warning: {e}")
        
        # 벡터 인덱스 생성 (Neo4j 5 문법) - 먼저 기존 인덱스 삭제 후 생성
        try:
            # 기존 벡터 인덱스 삭제
            drop_vector_index = "DROP INDEX sentence_vec IF EXISTS"
            self.graph.query(drop_vector_index)
            
            # 새 벡터 인덱스 생성
            vector_index_query = """
            CREATE VECTOR INDEX sentence_vec
            FOR (s:Sentence) ON (s.embedding)
            OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}
            """
            self.graph.query(vector_index_query)
            print("  ✅ Vector index created")
        except Exception as e:
            print(f"  ⚠️ Vector index warning: {e}")
            # 백업 방법으로 간단한 인덱스 생성 시도
            try:
                simple_index = "CREATE INDEX sentence_text IF NOT EXISTS FOR (s:Sentence) ON (s.text)"
                self.graph.query(simple_index)
                print("  ✅ Text index created as fallback")
            except Exception as e2:
                print(f"  ⚠️ Text index warning: {e2}")
    
    def build_graph_from_parser(self, parser: MedicalDocumentParser, document_title: str, document_url: str):
        """파서 객체로부터 그래프 구축"""
        print(f"🚀 Building graph from parsed document: {document_title}")
        
        # 1. 스키마 생성
        self.create_graph_schema()
        
        # 2. 문서 노드 생성
        self._create_document_node(document_title, document_url, parser.get_parsing_stats())
        
        # 3. 섹션 노드 생성
        print(f"📑 Creating {len(parser.sections)} section nodes...")
        for section in parser.sections:
            self._create_section_node(section, document_url)
        
        # 4. 문장 노드 생성 (배치 처리)
        print(f"📝 Creating {len(parser.sentences)} sentence nodes...")
        self._create_sentences_batch(parser.sentences, document_url)
        
        # 5. 벡터 스토어 인터페이스 생성
        self._create_vector_store()
        
        print(f"✅ Graph built successfully for: {document_title}")
    
    def build_graph_from_html(self, html_content: str, document_title: str, document_url: str):
        """HTML 내용으로부터 직접 그래프 구축"""
        print(f"📄 Parsing HTML document: {document_title}")
        
        # 파서 생성 및 실행
        parser = MedicalDocumentParser(document_url)
        parser.parse_html(html_content)
        
        # 파서 결과로 그래프 구축
        self.build_graph_from_parser(parser, document_title, document_url)
    
    def _create_document_node(self, title: str, url: str, stats: Dict):
        """문서 노드 생성"""
        # "- UpToDate" 제거한 핵심 제목만 저장
        clean_title = title.replace(' - UpToDate', '').strip()
        
        doc_query = """
        MERGE (d:Document {url: $url})
        SET d.title = $clean_title,
            d.created_at = datetime(),
            d.total_sections = $total_sections,
            d.total_sentences = $total_sentences,
            d.total_references = $total_references,
            d.total_images = $total_images,
            d.total_entities = $total_entities
        RETURN d
        """
        
        params = {
            "url": url,
            "clean_title": clean_title,
            "total_sections": stats.get("total_sections", 0),
            "total_sentences": stats.get("total_sentences", 0),
            "total_references": stats.get("total_references", 0),
            "total_images": stats.get("total_images", 0),
            "total_entities": stats.get("total_entities", 0)
        }
        
        self.graph.query(doc_query, params)
        print(f"  📄 Document node created with clean title: {clean_title}")
        
        # Title을 검색 가능한 문장으로 추가
        self._create_document_title_sentence(clean_title, url)
    
    def _create_document_title_sentence(self, clean_title: str, document_url: str):
        """문서 제목을 검색 가능한 문장으로 생성"""
        print(f"  🎯 Creating title sentence for: {clean_title}")
        
        try:
            # 제목 임베딩 생성
            title_embedding = self.embeddings.embed_documents([clean_title])[0]
            
            # 제목을 특별한 문장 노드로 생성
            title_sentence_query = """
            MATCH (d:Document {url: $doc_url})
            MERGE (title_sent:Sentence {id: $title_sentence_id})
            SET title_sent.text = $title_text,
                title_sent.section_name = "DOCUMENT_TITLE",
                title_sent.is_document_title = true,
                title_sent.embedding = $title_embedding,
                title_sent.created_at = datetime()
            MERGE (d)-[:HAS_TITLE_SENTENCE]->(title_sent)
            MERGE (d)-[:CONTAINS_SENTENCE]->(title_sent)
            RETURN title_sent
            """
            
            # 고유한 제목 문장 ID 생성
            title_hash = hashlib.md5(f"title_{document_url}".encode()).hexdigest()[:8]
            title_sentence_id = f"title_sent_{title_hash}"
            
            params = {
                "doc_url": document_url,
                "title_sentence_id": title_sentence_id,
                "title_text": clean_title,
                "title_embedding": title_embedding
            }
            
            self.graph.query(title_sentence_query, params)
            print(f"    ✅ Title sentence created with embedding")
            
            # 제목에서 의료 엔티티 추출하여 연결
            self._extract_title_entities(clean_title, title_sentence_id)
            
        except Exception as e:
            print(f"    ⚠️ Failed to create title sentence: {e}")
    
    def _extract_title_entities(self, title_text: str, sentence_id: str):
        """제목에서 의료 엔티티 추출하고 연결"""
        try:
            # 간단한 의료 엔티티 추출 (medical_parser의 로직을 간소화)
            words = title_text.lower().split()
            medical_terms = []
            
            # 중요한 의료 용어들 필터링
            for word in words:
                word_clean = word.strip('.,;:-()[]')
                if len(word_clean) > 3 and any(term in word_clean for term in [
                    'cancer', 'tumor', 'carcinoma', 'treatment', 'surgery', 'diagnosis',
                    'therapy', 'disease', 'syndrome', 'injury', 'trauma', 'hypogonadism',
                    'testicular', 'gallstone', 'reflux', 'lung', 'bladder', 'ileus',
                    'endovascular', 'metastases', 'nutrition', 'bowel', 'inflammatory'
                ]):
                    medical_terms.append(word_clean)
            
            # 의료 엔티티 노드 생성
            for entity in medical_terms:
                self._create_entity_node(entity, sentence_id)
            
            if medical_terms:
                print(f"    🏷️ Extracted {len(medical_terms)} entities from title: {medical_terms}")
                
        except Exception as e:
            print(f"    ⚠️ Title entity extraction error: {e}")
    
    def _create_section_node(self, section: MedicalSection, document_url: str):
        """섹션 노드 생성"""
        query = """
        MATCH (d:Document {url: $doc_url})
        MERGE (s:Section {id: $section_id})
        SET s.title = $title,
            s.content = $content,
            s.level = $level,
            s.created_at = datetime()
        MERGE (d)-[:CONTAINS_SECTION]->(s)
        RETURN s
        """
        
        params = {
            "doc_url": document_url,
            "section_id": section.section_id,
            "title": section.title,
            "content": section.content[:5000],  # 내용 길이 제한
            "level": section.level
        }
        
        self.graph.query(query, params)
    
    def _create_sentences_batch(self, sentences: List[MedicalSentence], document_url: str):
        """문장들을 배치로 처리하여 임베딩 효율성 향상"""
        
        if not sentences:
            print("⚠️ No sentences to process")
            return
        
        print(f"🔄 Processing {len(sentences)} sentences in batches...")
        
        # 배치 크기 설정 (OpenAI API 제한 고려)
        batch_size = 50  # 더 작은 배치로 안정성 향상
        
        for i in range(0, len(sentences), batch_size):
            batch = sentences[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(sentences) - 1) // batch_size + 1
            
            print(f"  📦 Processing batch {batch_num}/{total_batches} ({len(batch)} sentences)")
            
            # 참조 번호 제거 후 임베딩 생성
            clean_texts = []
            for sentence in batch:
                # 참조 번호 [1], [1,2] 등 제거
                clean_text = re.sub(r'\[\d+(?:,\d+)*\]', '', sentence.text).strip()
                # 너무 긴 텍스트는 자르기 (토큰 제한)
                if len(clean_text) > 8000:
                    clean_text = clean_text[:8000] + "..."
                clean_texts.append(clean_text)
            
            # 배치 임베딩 생성
            try:
                embeddings = self.embeddings.embed_documents(clean_texts)
                print(f"    ✅ Generated {len(embeddings)} embeddings")
            except Exception as e:
                print(f"    ❌ Embedding error: {e}")
                # 실패한 배치는 스킵하고 계속 진행
                continue
            
            # 문장 노드들 생성
            for sentence, embedding in zip(batch, embeddings):
                try:
                    self._create_sentence_node_with_embedding(sentence, document_url, embedding)
                except Exception as e:
                    print(f"    ⚠️ Error creating sentence node: {e}")
                    continue
    
    def _create_sentence_node_with_embedding(self, sentence: MedicalSentence, document_url: str, embedding: List[float]):
        """임베딩이 포함된 문장 노드 생성"""
        
        # 1. 문장 노드 생성
        sentence_query = """
        MATCH (d:Document {url: $doc_url})
        MERGE (sent:Sentence {id: $sentence_id})
        SET sent.text = $text,
            sent.section_name = $section,
            sent.embedding = $embedding,
            sent.created_at = datetime()
        MERGE (d)-[:CONTAINS_SENTENCE]->(sent)
        
        WITH sent, $section as section_title
        OPTIONAL MATCH (sec:Section) 
        WHERE sec.title = section_title
        FOREACH (s IN CASE WHEN sec IS NOT NULL THEN [sec] ELSE [] END |
            MERGE (s)-[:HAS_SENTENCE]->(sent)
        )
        
        RETURN sent
        """
        
        params = {
            "doc_url": document_url,
            "sentence_id": sentence.sentence_id,
            "text": sentence.text,
            "section": sentence.section,
            "embedding": embedding
        }
        
        self.graph.query(sentence_query, params)
        
        # 2. 참조문헌 연결
        for ref in sentence.references:
            self._create_reference_node(ref, sentence.sentence_id)
        
        # 3. 이미지 연결
        for img in sentence.images:
            self._create_image_node(img, sentence.sentence_id)
        
        # 4. 의료 엔티티 연결
        for entity in sentence.medical_entities:
            self._create_entity_node(entity, sentence.sentence_id)
    
    def _create_reference_node(self, reference: str, sentence_id: str):
        """참조문헌 노드 생성 (ID 충돌 방지)"""
        ref_parts = reference.split('|')
        ref_text = ref_parts[0] if ref_parts else reference
        ref_url = ref_parts[1] if len(ref_parts) > 1 else ""
        
        query = """
        MATCH (sent:Sentence {id: $sentence_id})
        MERGE (ref:Reference {id: $ref_id})
        SET ref.text = $text,
            ref.url = $url,
            ref.created_at = datetime()
        MERGE (sent)-[:CITES]->(ref)
        RETURN ref
        """
        
        # 고유한 참조 ID 생성
        ref_hash = hashlib.md5(reference.encode()).hexdigest()[:8]
        ref_id = f"ref_{ref_hash}"
        
        params = {
            "sentence_id": sentence_id,
            "ref_id": ref_id,
            "text": ref_text,
            "url": ref_url
        }
        
        self.graph.query(query, params)
    
    def _create_image_node(self, image_url: str, sentence_id: str):
        """이미지 노드 생성 (ID 충돌 방지)"""
        query = """
        MATCH (sent:Sentence {id: $sentence_id})
        MERGE (img:Image {id: $image_id})
        SET img.url = $url,
            img.description = $description,
            img.created_at = datetime()
        MERGE (sent)-[:REFERENCES_IMAGE]->(img)
        RETURN img
        """
        
        # 고유한 이미지 ID 생성
        img_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
        image_id = f"img_{img_hash}"
        
        # URL에서 설명 추출 시도
        description = ""
        if "imageKey=" in image_url:
            description = image_url.split("imageKey=")[1].split("&")[0]
        elif "topicKey=" in image_url:
            description = f"Image from {image_url.split('topicKey=')[1].split('&')[0]}"
        
        params = {
            "sentence_id": sentence_id,
            "image_id": image_id,
            "url": image_url,
            "description": description
        }
        
        self.graph.query(query, params)
    
    def _create_entity_node(self, entity: str, sentence_id: str):
        """의료 엔티티 노드 생성 (전역 고유성 유지)"""
        query = """
        MATCH (sent:Sentence {id: $sentence_id})
        MERGE (entity:MedicalEntity {name: $entity_name})
        SET entity.type = $entity_type,
            entity.created_at = datetime()
        MERGE (sent)-[:MENTIONS]->(entity)
        RETURN entity
        """
        
        # 엔티티 타입 분류
        entity_type = self._classify_entity_type(entity)
        
        params = {
            "sentence_id": sentence_id,
            "entity_name": entity.lower(),  # 전역적으로 고유하게 유지
            "entity_type": entity_type
        }
        
        self.graph.query(query, params)
    
    def _classify_entity_type(self, entity: str) -> str:
        """엔티티 타입 분류 (확장된 버전)"""
        entity_lower = entity.lower()
        
        # 수술/시술
        if any(term in entity_lower for term in ['pneumonectomy', 'lobectomy', 'surgery', 'resection', 'procedure', 'thoracotomy', 'intervention', 'treatment', 'therapy']):
            return 'procedure'
        # 질환/증상
        elif any(term in entity_lower for term in ['empyema', 'edema', 'fistula', 'syndrome', 'carcinoma', 'tumor', 'infection', 'cancer', 'disease', 'disorder', 'condition', 'infarction', 'hypertension', 'diabetes']):
            return 'condition'
        # 측정/검사/분석
        elif any(term in entity_lower for term in ['fev1', 'dlco', 'pps', 'ct', 'mri', 'radiograph', 'analysis', 'assessment', 'evaluation', 'study', 'trial', 'test', 'screening']):
            return 'measurement'
        # 해부학적 구조
        elif any(term in entity_lower for term in ['lung', 'bronchus', 'pleura', 'mediastinum', 'heart', 'ventricle', 'organ', 'tissue']):
            return 'anatomy'
        # 약물/치료
        elif any(term in entity_lower for term in ['amiodarone', 'sotalol', 'antibiotic', 'steroid', 'drug', 'medication', 'pharmaceutical']):
            return 'medication'
        # 경제/비용 관련 (cost-effectiveness 문서 특화)
        elif any(term in entity_lower for term in ['cost', 'economic', 'financial', 'budget', 'price', 'expense', 'qaly', 'utility', 'effectiveness', 'outcome', 'benefit']):
            return 'economic'
        # 시간/기간
        elif any(term in entity_lower for term in ['year', 'month', 'day', 'time', 'period', 'duration', 'horizon']):
            return 'temporal'
        # 수치/통계
        elif any(char.isdigit() for char in entity) or any(term in entity_lower for term in ['percent', 'rate', 'ratio', 'probability', 'risk', 'odds']):
            return 'numeric'
        # 방법론/접근법
        elif any(term in entity_lower for term in ['method', 'approach', 'technique', 'strategy', 'model', 'framework']):
            return 'methodology'
        else:
            return 'general'
    
    def _create_vector_store(self):
        """벡터 스토어 인터페이스 생성"""
        print("🔗 Creating vector store interface...")
        
        try:
            # 벡터 인덱스가 존재하는지 확인
            index_check = "SHOW INDEXES YIELD name WHERE name = 'sentence_vec'"
            index_exists = self.graph.query(index_check)
            
            if index_exists:
                # 기존 노드들을 활용한 벡터 스토어 인터페이스 생성
                self.vector_store = Neo4jVector(
                    embedding=self.embeddings,
                    graph=self.graph,
                    node_label="Sentence",
                    text_node_property="text",
                    embedding_node_property="embedding",
                    index_name="sentence_vec"
                )
                print("✅ Vector store interface created with vector index")
            else:
                print("⚠️ Vector index not found, creating fallback vector store")
                # 벡터 인덱스 없이 생성
                self.vector_store = Neo4jVector(
                    embedding=self.embeddings,
                    graph=self.graph,
                    node_label="Sentence",
                    text_node_property="text",
                    embedding_node_property="embedding"
                )
                print("✅ Vector store interface created without vector index")
        except Exception as e:
            print(f"⚠️ Vector store creation warning: {e}")
            self.vector_store = None

    def get_vector_store(self):
        """벡터 스토어 반환 (검색용)"""
        if not self.vector_store:
            try:
                self.vector_store = Neo4jVector(
                    embedding=self.embeddings,
                    graph=self.graph,
                    node_label="Sentence", 
                    text_node_property="text",
                    embedding_node_property="embedding"
                )
            except Exception as e:
                print(f"⚠️ Failed to create vector store: {e}")
                self.vector_store = None
        return self.vector_store
    
    def query_similar_sentences(self, query: str, k: int = 5) -> List[Dict]:
        """유사한 문장 검색 (벡터 검색)"""
        try:
            vector_store = self.get_vector_store()
            if vector_store:
                similar_docs = vector_store.similarity_search(query, k=k)
                
                results = []
                for doc in similar_docs:
                    results.append({
                        "text": doc.page_content,
                        "metadata": doc.metadata
                    })
                
                return results
            else:
                # 벡터 스토어가 없을 경우 텍스트 기반 검색 사용
                print("⚠️ Vector store not available, using text-based search")
                return self._fallback_text_search(query, k)
                
        except Exception as e:
            print(f"❌ Vector search error: {e}")
            # 벡터 검색 실패 시 텍스트 기반 검색으로 fallback
            print("🔄 Falling back to text-based search")
            return self._fallback_text_search(query, k)
    
    def _fallback_text_search(self, query: str, k: int = 5) -> List[Dict]:
        """벡터 검색 실패 시 사용할 텍스트 기반 검색"""
        clean_query = re.sub(r'\[\d+(?:,\d+)*\]', '', query.lower()).strip()
        
        fallback_query = """
        MATCH (sent:Sentence)
        WHERE toLower(sent.text) CONTAINS $search_term
        
        OPTIONAL MATCH (sec:Section)-[:HAS_SENTENCE]->(sent)
        
        RETURN sent.text as text,
               sec.title as section,
               sent.id as sentence_id
        ORDER BY length(sent.text) ASC
        LIMIT $limit
        """
        
        try:
            results = self.graph.query(fallback_query, {"search_term": clean_query, "limit": k})
            
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "text": result["text"],
                    "metadata": {
                        "section": result.get("section", "Unknown"),
                        "sentence_id": result.get("sentence_id", "")
                    }
                })
            
            return formatted_results
        except Exception as e:
            print(f"❌ Fallback search error: {e}")
            return []
    
    def query_graph_context(self, query: str, limit: int = 10) -> List[Dict]:
        """그래프 컨텍스트 검색 (관계 기반) - Title 포함 개선 버전"""
        clean_query = re.sub(r'\[\d+(?:,\d+)*\]', '', query.lower()).strip()
        
        # 쿼리를 단어별로 분리해서 더 유연한 검색
        query_words = [word.strip() for word in clean_query.split() if len(word.strip()) > 2]
        
        # 여러 검색 전략 시도 (Title 검색 포함)
        strategies = [
            # 전략 1: Document Title 직접 검색 (새로 추가)
            """
            MATCH (d:Document)
            WHERE any(word IN $query_words WHERE toLower(d.title) CONTAINS word)
            
            OPTIONAL MATCH (d)-[:HAS_TITLE_SENTENCE]->(title_sent:Sentence)
            OPTIONAL MATCH (title_sent)-[:MENTIONS]->(entity:MedicalEntity)
            
            RETURN title_sent.text as sentence,
                   title_sent.id as sentence_id,
                   "DOCUMENT_TITLE" as section,
                   collect(DISTINCT entity.name) as entities,
                   [] as references,
                   [] as images,
                   "title" as result_type
            ORDER BY title_sent.text
            LIMIT $limit
            """,
            
            # 전략 2: 엔티티 이름으로 직접 검색
            """
            MATCH (entity:MedicalEntity)-[:MENTIONS]-(sent:Sentence)
            WHERE any(word IN $query_words WHERE toLower(entity.name) CONTAINS word)
            
            OPTIONAL MATCH (sent)-[:CITES]->(ref:Reference)
            OPTIONAL MATCH (sent)-[:REFERENCES_IMAGE]->(img:Image)
            OPTIONAL MATCH (sec:Section)-[:HAS_SENTENCE]->(sent)
            
            RETURN sent.text as sentence, 
                   sent.id as sentence_id,
                   COALESCE(sec.title, sent.section_name) as section,
                   collect(DISTINCT entity.name) as entities,
                   collect(DISTINCT {text: ref.text, url: ref.url}) as references,
                   collect(DISTINCT {url: img.url, description: img.description}) as images,
                   "entity" as result_type
            ORDER BY size(entities) DESC
            LIMIT $limit
            """,
            
            # 전략 3: 문장 텍스트에서 단어별 검색 (Title 문장 포함)
            """
            MATCH (sent:Sentence)
            WHERE any(word IN $query_words WHERE toLower(sent.text) CONTAINS word)
            
            OPTIONAL MATCH (sent)-[:MENTIONS]->(entity:MedicalEntity)
            OPTIONAL MATCH (sent)-[:CITES]->(ref:Reference)
            OPTIONAL MATCH (sent)-[:REFERENCES_IMAGE]->(img:Image)
            OPTIONAL MATCH (sec:Section)-[:HAS_SENTENCE]->(sent)
            
            WITH sent, sec, collect(DISTINCT entity.name) as entities,
                 collect(DISTINCT {text: ref.text, url: ref.url}) as references,
                 collect(DISTINCT {url: img.url, description: img.description}) as images
            
            RETURN sent.text as sentence, 
                   sent.id as sentence_id,
                   COALESCE(sec.title, sent.section_name) as section,
                   entities,
                   references,
                   images,
                   CASE WHEN sent.is_document_title = true THEN "title" ELSE "sentence" END as result_type
            ORDER BY CASE WHEN sent.is_document_title = true THEN 0 ELSE 1 END, size(entities) DESC
            LIMIT $limit
            """,
            
            # 전략 4: 원래 방식 (전체 쿼리 텍스트)
            """
            MATCH (sent:Sentence)
            WHERE toLower(sent.text) CONTAINS $search_term
            
            OPTIONAL MATCH (sent)-[:MENTIONS]->(entity:MedicalEntity)
            OPTIONAL MATCH (sent)-[:CITES]->(ref:Reference)
            OPTIONAL MATCH (sent)-[:REFERENCES_IMAGE]->(img:Image)
            OPTIONAL MATCH (sec:Section)-[:HAS_SENTENCE]->(sent)
            
            WITH sent, sec, collect(DISTINCT entity.name) as entities,
                 collect(DISTINCT {text: ref.text, url: ref.url}) as references,
                 collect(DISTINCT {url: img.url, description: img.description}) as images
            
            RETURN sent.text as sentence, 
                   sent.id as sentence_id,
                   COALESCE(sec.title, sent.section_name) as section,
                   entities,
                   references,
                   images,
                   CASE WHEN sent.is_document_title = true THEN "title" ELSE "sentence" END as result_type
            ORDER BY CASE WHEN sent.is_document_title = true THEN 0 ELSE 1 END, size(entities) DESC
            LIMIT $limit
            """
        ]
        
        # 각 전략을 차례로 시도
        for i, strategy in enumerate(strategies, 1):
            try:
                if i <= 3:  # 단어별 검색 (전략 1, 2, 3)
                    params = {"query_words": query_words, "limit": limit}
                else:  # 전체 쿼리 검색 (전략 4)
                    params = {"search_term": clean_query, "limit": limit}
                
                results = self.graph.query(strategy, params)
                
                if results:
                    strategy_name = ["Title", "Entity", "Sentence", "Fallback"][i-1]
                    print(f"  ✅ 그래프 검색 전략 {i} ({strategy_name}) 성공: {len(results)}개 결과")
                    return results
                    
            except Exception as e:
                strategy_name = ["Title", "Entity", "Sentence", "Fallback"][i-1]
                print(f"  ⚠️ 그래프 검색 전략 {i} ({strategy_name}) 실패: {e}")
                continue
        
        print(f"  ❌ 모든 그래프 검색 전략 실패")
        return []
    
    def get_document_stats(self) -> Dict:
        """문서 통계 조회"""
        stats_query = """
        MATCH (d:Document)
        OPTIONAL MATCH (d)-[:CONTAINS_SECTION]->(sec:Section)
        OPTIONAL MATCH (d)-[:CONTAINS_SENTENCE]->(sent:Sentence)
        OPTIONAL MATCH (sent)-[:MENTIONS]->(entity:MedicalEntity)
        OPTIONAL MATCH (sent)-[:CITES]->(ref:Reference)
        OPTIONAL MATCH (sent)-[:REFERENCES_IMAGE]->(img:Image)
        
        RETURN d.title as document_title,
               d.url as document_url,
               count(DISTINCT sec) as total_sections,
               count(DISTINCT sent) as total_sentences,
               count(DISTINCT entity) as total_entities,
               count(DISTINCT ref) as total_references,
               count(DISTINCT img) as total_images
        """
        
        try:
            results = self.graph.query(stats_query)
            return results[0] if results else {}
        except Exception as e:
            print(f"❌ Stats query error: {e}")
            return {}

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
                    "images": []
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
                    "references": [ref for ref in result.get("references", []) if ref.get("text")],
                    "images": [img for img in result.get("images", []) if img.get("url")]
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
    
    def query_with_images(self, query: str, k_vector: int = 5, k_graph: int = 10, k_images: int = 5) -> Dict[str, Any]:
        """텍스트 + 이미지 통합 검색"""
        print(f"🔍 통합 검색 (텍스트 + 이미지): {query}")
        
        # 1. 기본 텍스트 검색
        text_results = self.query(query, k_vector=k_vector, k_graph=k_graph)
        
        # 2. 이미지 검색
        image_results = self.query_related_images(query, limit=k_images)
        
        # 3. 결과 통합
        combined_results = text_results.copy()
        combined_results["image_results"] = image_results
        combined_results["total_images_found"] = len(image_results)
        
        # 4. 이미지 요약 정보 추가
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
        
        print(f"📊 통합 결과: 텍스트 {len(text_results['combined_sentences'])}개, 이미지 {len(image_results)}개")
        
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
    
    # 성공/실패 통계
    successful_files = []
    failed_files = []
    
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
                            if i == 0:
                                # 첫 번째 파일로 RAG 시스템 초기화
                                f.write(f"🏗️ Initializing RAG system with: {file_name}\n")
                                builder, query_engine = build_medical_rag_from_json(json_file)
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
        if successful_files:
            total_stats = builder.get_document_stats()
            print(f"\n📈 Combined Database Statistics:")
            for key, value in total_stats.items():
                print(f"  {key}: {value}")
        
        print(f"\n📝 Detailed logs saved to: {log_file}")
        print(f"✅ Multi-document RAG system ready with {len(successful_files)} documents!")
    
    if not successful_files:
        raise RuntimeError("No files were successfully processed")
    
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
                results = query_engine.query(query, k_vector=3, k_graph=3)
                
                vector_count = results['query_info']['vector_results_count']
                graph_count = results['query_info']['graph_results_count']
                print(f"📊 Results: {vector_count} vector + {graph_count} graph")
                
                # 상위 결과 출력
                if results['combined_sentences']:
                    top_result = results['combined_sentences'][0]
                    print(f"🎯 Top result: {top_result['text'][:100]}...")
                    print(f"   Section: {top_result['section']}")
                    print(f"   Source: {top_result['source']}")
                    if top_result['entities']:
                        print(f"   Entities: {', '.join(top_result['entities'][:3])}")
        
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