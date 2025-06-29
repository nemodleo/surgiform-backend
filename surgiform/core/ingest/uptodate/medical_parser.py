"""
UpToDate 의료 문서 파서
HTML 문서를 파싱하여 섹션, 문장, 참조문헌, 이미지 정보를 추출
"""

import re
import hashlib
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from bs4 import BeautifulSoup

@dataclass
class MedicalSentence:
    """의료 문장 정보"""
    text: str
    section: str
    references: List[Dict[str, str]]
    images: List[Dict[str, str]]
    tables: List[Dict[str, str]]
    medical_entities: List[str]
    sentence_id: str

@dataclass
class MedicalSection:
    """의료 섹션 정보"""
    title: str
    content: str
    level: int  # h1=1, h2=2, etc.
    section_id: str

class MedicalDocumentParser:
    """UpToDate 의료 문서 파서"""
    
    def __init__(self, document_url: str = ""):
        self.soup = None
        self.sections = []
        self.sentences = []
        self.doc_hash = hashlib.md5(document_url.encode()).hexdigest()[:8] if document_url else "default"
        
    def parse_html(self, html_content: str) -> None:
        """HTML 문서 파싱 - 메인 진입점"""
        print(f"🔄 Starting HTML parsing...")
        
        self.soup = BeautifulSoup(html_content, 'html.parser')
        self._extract_sections()
        self._extract_sentences()
        
        print(f"✅ Parsing complete: {len(self.sections)} sections, {len(self.sentences)} sentences")
    
    def _extract_sections(self) -> None:
        """섹션 추출 (UpToDate 실제 구조에 맞게)"""
        print("📑 Extracting sections...")
        sections = []
        
        # UpToDate의 실제 제목 구조: <p class="headingAnchor css_h1|css_h2">
        headings = self.soup.find_all(lambda tag: 
            tag.name == 'p' and 
            tag.has_attr('class') and 
            'headingAnchor' in ' '.join(tag['class'])
        )
        
        print(f"📋 Found {len(headings)} headings")
        
        for i, heading in enumerate(headings):
            # 제목 텍스트 추출 - span.h1 또는 span.h2에서
            title_span = heading.find('span', class_=lambda x: x and ('h1' in x or 'h2' in x))
            title = title_span.get_text(strip=True) if title_span else heading.get_text(strip=True)
            
            # 빈 제목 스킵
            if not title or len(title.strip()) < 2:
                continue
            
            # 섹션 레벨 결정 (css_h1=1, css_h2=2)
            level = 1 if 'css_h1' in ' '.join(heading['class']) else 2
            
            # 섹션 ID - 문서별 고유하게 생성
            raw_id = heading.get('id', f'section_{i}')
            section_id = f"{self.doc_hash}_{raw_id}"
            
            # 다음 제목까지의 내용 추출
            content = self._extract_section_content(heading, headings, i)
            
            section = MedicalSection(
                title=title,
                content=content,
                level=level,
                section_id=section_id
            )
            sections.append(section)
            
            print(f"  📄 Section {i+1}: {title[:50]}{'...' if len(title) > 50 else ''}")
        
        self.sections = sections
        print(f"✅ Extracted {len(sections)} sections")
    
    def _extract_section_content(self, heading, all_headings: List, current_index: int) -> str:
        """섹션 내용 추출"""
        content_elements = []
        current = heading.find_next_sibling()
        next_heading = all_headings[current_index + 1] if current_index + 1 < len(all_headings) else None
        
        while current and current != next_heading:
            if current.name in ['p', 'ul', 'ol', 'div'] and current.get_text(strip=True):
                # 참조 번호 제거해서 깔끔한 내용만 
                text = current.get_text(strip=True)
                clean_text = re.sub(r'\[\d+(?:,\d+)*\]', '', text)
                if clean_text.strip() and len(clean_text.strip()) > 10:
                    content_elements.append(clean_text.strip())
            current = current.find_next_sibling()
        
        return '\n'.join(content_elements)
    
    def _extract_sentences(self) -> None:
        """문장별로 추출하고 참조문헌, 이미지, 테이블 정보 포함"""
        print("📝 Extracting sentences...")
        sentences = []
        sentence_id = 0
        
        # 다양한 문단 클래스 찾기
        paragraph_classes = ['css_h1', 'css_h2', 'bulletIndent1', 'bulletIndent2', 'inlineGraphicParagraph']
        
        paragraphs = []
        for cls in paragraph_classes:
            found_paras = self.soup.find_all('p', class_=lambda x: x and cls in x)
            paragraphs.extend(found_paras)
        
        # 중복 제거 (같은 문단이 여러 클래스를 가질 수 있음)
        paragraphs = list(set(paragraphs))
        
        print(f"📄 Found {len(paragraphs)} paragraphs")
        
        for para_idx, para in enumerate(paragraphs):
            if para_idx % 50 == 0:
                print(f"  🔄 Processing paragraph {para_idx + 1}/{len(paragraphs)}")
            
            # 현재 섹션 찾기
            current_section = self._find_section_for_element(para)
            
            # 문단 텍스트 추출
            para_text = para.get_text(strip=True)
            if not para_text or len(para_text) < 20:
                continue
            
            # 요소들 먼저 추출 (문장 분리 전에)
            references = self._extract_references_from_element(para)
            images = self._extract_images_from_element(para)
            tables = self._extract_tables_from_element(para)
            
            # 문장에서 참조 번호 제거 후 분리
            clean_text = self._clean_sentence_references(para_text)
            sentences_in_para = self._split_sentences(clean_text)
            
            for sentence_text in sentences_in_para:
                if len(sentence_text.strip()) < 15:  # 너무 짧은 문장 제외
                    continue
                
                # 의료 엔티티 추출
                medical_entities = self._extract_medical_entities(sentence_text)
                
                # 문장 ID - 문서별 고유하게 생성
                unique_sentence_id = f"{self.doc_hash}_sent_{sentence_id}"
                
                sentence = MedicalSentence(
                    text=sentence_text.strip(),
                    section=current_section,
                    references=references,
                    images=images,
                    tables=tables,
                    medical_entities=medical_entities,
                    sentence_id=unique_sentence_id
                )
                sentences.append(sentence)
                sentence_id += 1
        
        self.sentences = sentences
        print(f"✅ Extracted {len(sentences)} sentences")
    
    def _find_section_for_element(self, element) -> str:
        """요소가 속한 섹션 찾기 (UpToDate 구조에 맞게)"""
        # 이전 제목 찾기 - p.headingAnchor 형태
        heading = element.find_previous('p', class_=lambda x: x and 'headingAnchor' in x)
        if heading:
            title_span = heading.find('span', class_=lambda x: x and ('h1' in x or 'h2' in x))
            if title_span:
                return title_span.get_text(strip=True)
            else:
                # span이 없는 경우 전체 텍스트에서 추출
                heading_text = heading.get_text(strip=True)
                # 제목에서 불필요한 기호 제거
                clean_title = re.sub(r'^[^\w]*|[^\w]*$', '', heading_text)
                return clean_title if clean_title else "Unknown Section"
        return "Unknown Section"
    
    def _split_sentences(self, text: str) -> List[str]:
        """문장 분리 (개선된 버전)"""
        # 의료 문서 특성을 고려한 문장 분리
        # 약어 뒤의 마침표는 문장 끝이 아님
        abbreviations = ['Dr', 'Mr', 'Ms', 'vs', 'eg', 'ie', 'etc', 'al', 'FEV1', 'DLCO', 'PPS']
        
        # 약어 보호
        protected_text = text
        for abbr in abbreviations:
            protected_text = protected_text.replace(f'{abbr}.', f'{abbr}<!PERIOD!>')
        
        # 문장 분리
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', protected_text)
        
        # 약어 복원 및 정리
        result = []
        for sentence in sentences:
            restored = sentence.replace('<!PERIOD!>', '.')
            cleaned = restored.strip()
            if cleaned and len(cleaned) > 10:
                result.append(cleaned)
        
        return result
    
    def _clean_sentence_references(self, text: str) -> str:
        """문장에서 참조 번호와 기호 제거 (강화된 버전)"""
        clean_text = text
        
        # 1. 대괄호 참조 번호 제거 [1], [1,2], [1-3], [1,2,3] 등
        clean_text = re.sub(r'\[\d+(?:[,-]\d+)*\]', '', clean_text)
        
        # 2. 소괄호 내 테이블/이미지/그림 참조 제거 
        # (table 1), (image 2), (figure 3), (graphic 1) 등
        clean_text = re.sub(r'\(\s*(?:table|image|figure|graphic|chart|algorithm)\s+\d+\s*\)', '', clean_text, flags=re.IGNORECASE)
        
        # 2-1. 연속된 figure/image/table 참조 제거 (공백 없는 경우)
        # (figure 1andfigure 2), (image 1andimage 2) 등
        clean_text = re.sub(r'\(\s*(?:figure|image|table)\s*\d+\s*(?:and|,)\s*(?:figure|image|table)\s*\d+\s*\)', '', clean_text, flags=re.IGNORECASE)
        
        # 2-2. 3개 이상의 연속 참조 제거 (table 1, table 2, table 3)
        clean_text = re.sub(r'\(\s*(?:figure|image|table)\s*\d+(?:\s*,\s*(?:figure|image|table)?\s*\d+)*\s*\)', '', clean_text, flags=re.IGNORECASE)
        
        # 3. see 참조 제거 (see "제목")
        clean_text = re.sub(r'\(see\s*"[^"]*"\s*\)', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'\.\s*\(see\s*"[^"]*"[^)]*\)', '.', clean_text, flags=re.IGNORECASE)
        
        # 4. 고립된 단일 숫자 제거 (문맥상 참조로 보이는)
        # 단, 의미있는 수치는 보존 (나이, 퍼센트, 용량 등)
        clean_text = re.sub(r'\s+\[\s*\d+\s*\]\s*', ' ', clean_text)
        clean_text = re.sub(r'\s+\(\s*\d+\s*\)\s*(?![%mg/mLkg])', ' ', clean_text)
        
        # 5. 특수 문자들 정리
        # 연속된 점들 제거 (..., ..)
        clean_text = re.sub(r'\.{2,}', '.', clean_text)
        
        # 연속된 쉼표 제거
        clean_text = re.sub(r',{2,}', ',', clean_text)
        
        # 문장 시작/끝의 불필요한 구두점 제거
        clean_text = re.sub(r'^[,;:\-\s]+', '', clean_text)
        clean_text = re.sub(r'[,;:\-\s]+$', '', clean_text)
        
        # 6. 공백 정리
        # 연속된 공백을 단일 공백으로
        clean_text = re.sub(r'\s+', ' ', clean_text)
        
        # 구두점 앞의 불필요한 공백 제거
        clean_text = re.sub(r'\s+([,.;:!?])', r'\1', clean_text)
        
        # 앞뒤 공백 제거
        clean_text = clean_text.strip()
        
        # 7. 빈 괄호나 대괄호 제거
        clean_text = re.sub(r'\(\s*\)', '', clean_text)
        clean_text = re.sub(r'\[\s*\]', '', clean_text)
        
        # 8. 최종 정리 - 다시 한번 연속 공백 제거
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        return clean_text
    
    def _extract_references_from_element(self, element) -> List[Dict[str, str]]:
        """요소에서 참조문헌 추출 (URL과 함께)"""
        references = []
        
        # 참조 링크 찾기 (다양한 패턴)
        ref_selectors = [
            'a.abstract_t',  # 일반 참조
            'a[href*="/abstract/"]',  # 추상 링크
            'a[class*="reference"]'  # 참조 클래스
        ]
        
        for selector in ref_selectors:
            ref_links = element.select(selector)
            for link in ref_links:
                ref_text = link.get_text(strip=True)
                href = link.get('href', '')
                
                # 참조 번호 추출
                ref_number = self._extract_reference_number(ref_text, href)
                
                if ref_text and href:
                    references.append({
                        'id': ref_number,
                        'text': ref_text,
                        'url': href,
                        'type': 'reference'
                    })
        
        # 텍스트에서 참조 번호 패턴으로도 찾기
        text = element.get_text()
        ref_numbers = re.findall(r'\[(\d+(?:,\d+)*)\]', text)
        for ref_num_str in ref_numbers:
            for num in ref_num_str.split(','):
                num = num.strip()
                if num and num not in [r['id'] for r in references]:
                    references.append({
                        'id': num,
                        'text': f'Reference {num}',
                        'url': f'#ref{num}',  # 기본 앵커
                        'type': 'reference'
                    })
        
        return self._deduplicate_references(references)
    
    def _extract_reference_number(self, text: str, url: str) -> str:
        """참조문헌에서 번호 추출"""
        # URL에서 번호 추출 시도
        url_num = re.search(r'abstract/(\d+)', url)
        if url_num:
            return url_num.group(1)
        
        # 텍스트에서 번호 추출 시도
        text_num = re.search(r'(\d+)', text)
        if text_num:
            return text_num.group(1)
        
        # 기본값
        return hashlib.md5(f"{text}_{url}".encode()).hexdigest()[:8]
    
    def _extract_images_from_element(self, element) -> List[Dict[str, str]]:
        """요소에서 이미지 정보 추출 (URL과 함께)"""
        images = []
        
        # 1. 일반 이미지 링크
        img_links = element.find_all('a', class_=lambda x: x and 'graphic' in x)
        for link in img_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            if href and 'image' in href:
                img_id = self._extract_image_id(href, text)
                images.append({
                    'id': img_id,
                    'url': href,
                    'description': text or f'Image {img_id}',
                    'type': 'image'
                })
        
        # 2. 인라인 그래픽 템플릿 
        templates = element.find_next_siblings('template', limit=3)
        for template in templates:
            url = template.get('url', '')
            if url and 'image' in url:
                img_id = self._extract_image_id(url, '')
                images.append({
                    'id': img_id,
                    'url': url,
                    'description': f'Inline Image {img_id}',
                    'type': 'image'
                })
        
        # 3. data 속성의 이미지 정보
        data_imgs = element.find_all(attrs={'data-inline-graphics': True})
        for img_elem in data_imgs:
            graphic_id = img_elem.get('data-inline-graphics')
            if graphic_id:
                img_url = f"/contents/image?imageKey={graphic_id}"
                images.append({
                    'id': graphic_id,
                    'url': img_url,
                    'description': f'Graphic {graphic_id}',
                    'type': 'image'
                })
        
        # 4. 텍스트에서 이미지 참조 번호 찾기
        text = element.get_text()
        img_numbers = re.findall(r'\(\s*image\s+(\d+)\s*\)', text, re.IGNORECASE)
        for img_num in img_numbers:
            if img_num not in [img['id'] for img in images]:
                images.append({
                    'id': img_num,
                    'url': f'#image{img_num}',
                    'description': f'Image {img_num}',
                    'type': 'image'
                })
        
        return self._deduplicate_images(images)
    
    def _extract_image_id(self, url: str, text: str) -> str:
        """이미지 URL에서 ID 추출"""
        # imageKey 파라미터에서 추출
        key_match = re.search(r'imageKey=([^&]+)', url)
        if key_match:
            return key_match.group(1)
        
        # 텍스트에서 번호 추출
        text_num = re.search(r'(\d+)', text)
        if text_num:
            return text_num.group(1)
        
        # URL 해시
        return hashlib.md5(url.encode()).hexdigest()[:8]
    
    def _extract_tables_from_element(self, element) -> List[Dict[str, str]]:
        """요소에서 테이블 정보 추출 (새로 추가)"""
        tables = []
        
        # 1. 테이블 링크 찾기
        table_links = element.find_all('a', href=re.compile(r'.*table.*|.*graphic.*'))
        for link in table_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # 테이블 관련 키워드 확인
            if any(keyword in text.lower() for keyword in ['table', 'chart', 'algorithm']):
                table_id = self._extract_table_id(href, text)
                tables.append({
                    'id': table_id,
                    'url': href,
                    'title': text or f'Table {table_id}',
                    'type': 'table'
                })
        
        # 2. 텍스트에서 테이블 참조 번호 찾기
        text = element.get_text()
        table_numbers = re.findall(r'\(\s*table\s+(\d+)\s*\)', text, re.IGNORECASE)
        for table_num in table_numbers:
            if table_num not in [tbl['id'] for tbl in tables]:
                tables.append({
                    'id': table_num,
                    'url': f'#table{table_num}',
                    'title': f'Table {table_num}',
                    'type': 'table'
                })
        
        # 3. 실제 table 태그 찾기
        actual_tables = element.find_all('table')
        for i, table in enumerate(actual_tables):
            table_id = table.get('id', f'table_{i}')
            caption = table.find('caption')
            title = caption.get_text(strip=True) if caption else f'Table {table_id}'
            
            tables.append({
                'id': table_id,
                'url': f'#table_{table_id}',
                'title': title,
                'type': 'table'
            })
        
        return self._deduplicate_tables(tables)
    
    def _extract_table_id(self, url: str, text: str) -> str:
        """테이블 URL에서 ID 추출"""
        # URL에서 테이블 ID 추출
        table_match = re.search(r'table[_-]?(\d+)|graphic[_-]?(\d+)', url)
        if table_match:
            return table_match.group(1) or table_match.group(2)
        
        # 텍스트에서 번호 추출
        text_num = re.search(r'(\d+)', text)
        if text_num:
            return text_num.group(1)
        
        # URL 해시
        return hashlib.md5(url.encode()).hexdigest()[:8]
    
    def _deduplicate_references(self, references: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """참조문헌 중복 제거"""
        seen = set()
        unique_refs = []
        for ref in references:
            key = f"{ref['id']}_{ref['url']}"
            if key not in seen:
                seen.add(key)
                unique_refs.append(ref)
        return unique_refs
    
    def _deduplicate_images(self, images: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """이미지 중복 제거"""
        seen = set()
        unique_imgs = []
        for img in images:
            key = f"{img['id']}_{img['url']}"
            if key not in seen:
                seen.add(key)
                unique_imgs.append(img)
        return unique_imgs
    
    def _deduplicate_tables(self, tables: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """테이블 중복 제거"""
        seen = set()
        unique_tables = []
        for table in tables:
            key = f"{table['id']}_{table['url']}"
            if key not in seen:
                seen.add(key)
                unique_tables.append(table)
        return unique_tables
    
    def _extract_medical_entities(self, text: str) -> List[str]:
        """의료 엔티티 추출 (확장된 패턴)"""
        entities = []
        
        # 의료 용어 패턴들 (더 포괄적 - cost-effectiveness 문서 특화)
        patterns = [
            # 수술/시술/치료
            r'\b(?:pneumonectomy|lobectomy|thoracotomy|thoracoscopy|resection|surgery|procedure|intervention|treatment|therapy|operation)\b',
            
            # 질환/합병증
            r'\b(?:empyema|edema|fistula|syndrome|carcinoma|tumor|cancer|infection|hemorrhage|disease|disorder|condition|complication|morbidity|mortality)\b',
            
            # 측정/검사/분석
            r'\b(?:FEV1|DLCO|PPS|ARDS|CT|MRI|chest\s+radiograph|echocardiography|analysis|assessment|evaluation|study|trial|test|screening|examination)\b',
            
            # 심혈관 관련
            r'\b(?:atrial fibrillation|myocardial infarction|pulmonary embolism|arrhythmia|tachycardia|cardiovascular|cardiac)\b',
            
            # 해부학적 구조
            r'\b(?:lung|bronchus|pleura|mediastinum|diaphragm|pericardium|ventricle|organ|tissue|anatomical)\b',
            
            # 경제/비용 분석 용어 (cost-effectiveness 특화)
            r'\b(?:cost-effectiveness|cost-utility|cost-benefit|QALY|DALY|evLYG|GRA-QALY|economic|financial|budget|expenditure|expense|price|outcome|benefit|utility|value)\b',
            
            # 연구/방법론
            r'\b(?:randomized|controlled|trial|study|meta-analysis|systematic\s+review|cohort|case-control|observational|prospective|retrospective|evidence|research)\b',
            
            # 통계/수치/지표
            r'\b(?:mortality\s+rate|morbidity\s+rate|survival\s+rate|risk\s+ratio|odds\s+ratio|hazard\s+ratio|confidence\s+interval|p-value|statistics|probability|percentage)\b',
            
            # 시간/기간
            r'\b(?:life\s+expectancy|survival|follow-up|time\s+horizon|discount\s+rate|long-term|short-term|annual|yearly|monthly)\b',
            
            # 단위가 있는 수치
            r'\b\d+\s*(?:percent|%|mg|mL|years?|months?|days?|hours?|minutes?|dollars?|\$|USD|EUR)\b',
            
            # 약물/의료기기
            r'\b(?:amiodarone|sotalol|antibiotics|analgesics|steroids|medication|drug|pharmaceutical|device|implant|prosthesis)\b',
            
            # 의료 전문 용어
            r'\b(?:diagnosis|prognosis|etiology|pathophysiology|epidemiology|prevalence|incidence|sensitivity|specificity|efficacy|effectiveness|safety)\b'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            # 매치 결과 처리 - 튜플이면 합치고, 문자열이면 그대로
            for match in matches:
                if isinstance(match, tuple):
                    entity = ' '.join(match).lower().strip()
                else:
                    entity = match.lower().strip()
                
                if entity and len(entity) > 1:
                    entities.append(entity)
        
        # 추가적으로 의료/경제 용어 단어 단위로 추출
        medical_keywords = [
            'patient', 'clinical', 'medical', 'health', 'healthcare', 'hospital', 'physician', 'doctor', 'nurse',
            'quality', 'safety', 'risk', 'benefit', 'outcome', 'result', 'effect', 'impact', 'improvement',
            'cost', 'economic', 'financial', 'budget', 'resource', 'allocation', 'efficiency', 'value',
            'analysis', 'evaluation', 'assessment', 'comparison', 'study', 'research', 'evidence',
            'mortality', 'morbidity', 'survival', 'life', 'death', 'disability', 'functional', 'status'
        ]
        
        # 단어 단위로 키워드 찾기
        words = re.findall(r'\b\w+\b', text.lower())
        for word in words:
            if word in medical_keywords and len(word) > 3:
                entities.append(word)
        
        # 중복 제거 및 필터링
        unique_entities = []
        seen = set()
        for entity in entities:
            entity_clean = entity.strip()
            if (len(entity_clean) > 2 and 
                entity_clean not in seen and 
                not entity_clean.isdigit() and  # 순수 숫자 제외
                not all(c in '.,;:!?' for c in entity_clean)):  # 구두점만 있는 것 제외
                unique_entities.append(entity_clean)
                seen.add(entity_clean)
        
        return unique_entities

    def get_parsing_stats(self) -> Dict:
        """파싱 통계 반환"""
        stats = {
            "document_hash": self.doc_hash,
            "total_sections": len(self.sections),
            "total_sentences": len(self.sentences),
            "sections_by_level": {},
            "sentences_by_section": {},
            "total_references": 0,
            "total_images": 0,
            "total_tables": 0,
            "total_entities": 0
        }
        
        # 섹션별 통계
        for section in self.sections:
            level = section.level
            stats["sections_by_level"][level] = stats["sections_by_level"].get(level, 0) + 1
        
        # 문장별 통계
        for sentence in self.sentences:
            section = sentence.section
            stats["sentences_by_section"][section] = stats["sentences_by_section"].get(section, 0) + 1
            stats["total_references"] += len(sentence.references)
            stats["total_images"] += len(sentence.images)
            stats["total_tables"] += len(sentence.tables)
            stats["total_entities"] += len(sentence.medical_entities)
        
        return stats

    def export_parsed_data(self, output_path: str = None) -> Dict:
        """파싱된 데이터 내보내기"""
        data = {
            "document_info": {
                "hash": self.doc_hash,
                "parsing_stats": self.get_parsing_stats()
            },
            "sections": [
                {
                    "id": section.section_id,
                    "title": section.title,
                    "content": section.content,
                    "level": section.level
                }
                for section in self.sections
            ],
            "sentences": [
                {
                    "id": sentence.sentence_id,
                    "text": sentence.text,
                    "section": sentence.section,
                    "references": sentence.references,
                    "images": sentence.images,
                    "tables": sentence.tables,
                    "medical_entities": sentence.medical_entities
                }
                for sentence in self.sentences
            ]
        }
        
        if output_path:
            import json
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"💾 Parsed data exported to {output_path}")
        
        return data

# 헬퍼 함수들
def load_uptodate_document(file_path: str) -> str:
    """UpToDate HTML 문서 로드"""
    print(f"📂 Loading document from {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    print(f"✅ Document loaded ({len(content)} characters)")
    return content

def extract_document_info(html_content: str) -> Tuple[str, str]:
    """문서에서 제목과 URL 추출"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 제목 추출
    title_div = soup.find('div', id='topicTitle')
    title = title_div.get_text(strip=True) if title_div else "Unknown Title"
    
    # URL 생성 (실제 URL이 있다면 그것을 사용)
    url = f"https://www.uptodate.com/contents/{title.lower().replace(' ', '-').replace(',', '')}"
    
    print(f"📋 Document title: {title}")
    print(f"🔗 Generated URL: {url}")
    
    return title, url

def parse_uptodate_file(file_path: str) -> MedicalDocumentParser:
    """UpToDate 파일을 파싱하는 편의 함수"""
    # 문서 로드
    html_content = load_uptodate_document(file_path)
    title, url = extract_document_info(html_content)
    
    # 파서 생성 및 실행
    parser = MedicalDocumentParser(url)
    parser.parse_html(html_content)
    
    # 통계 출력
    stats = parser.get_parsing_stats()
    print(f"\n📊 Parsing Statistics:")
    print(f"  📑 Sections: {stats['total_sections']}")
    print(f"  📝 Sentences: {stats['total_sentences']}")
    print(f"  📚 References: {stats['total_references']}")
    print(f"  🖼️ Images: {stats['total_images']}")
    print(f"  📊 Tables: {stats['total_tables']}")
    print(f"  🏷️ Medical Entities: {stats['total_entities']}")
    
    return parser

if __name__ == "__main__":
    # 테스트 실행
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        parser = parse_uptodate_file(file_path)
        
        # JSON으로 내보내기
        output_file = file_path.replace('.html', '_parsed.json')
        parser.export_parsed_data(output_file)
    else:
        print("Usage: python medical_parser.py <uptodate_html_file>")