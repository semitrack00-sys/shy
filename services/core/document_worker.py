"""Fixed document parser child. No caller-chosen command, path, URL or file writes."""
from __future__ import annotations
import base64
from contextlib import contextmanager
import re
import hashlib
import io
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

MAX_BYTES=1024*1024
MAX_CHARS=100_000
MAX_TEXT_BYTES=256*1024

def extract_pdf(raw):
    from pypdf import PdfReader
    if not raw.startswith(b'%PDF-'): raise ValueError('invalid_pdf_signature')
    reader=PdfReader(io.BytesIO(raw),strict=True)
    if reader.is_encrypted: raise ValueError('encrypted_pdf_not_supported')
    if not 1 <= len(reader.pages) <= 25: raise ValueError('pdf_page_limit_25')
    parts=[]; found=False; size=0
    for number,page in enumerate(reader.pages,1):
        stream=page.get_contents()
        if stream is not None and len(stream.get_data()) > 4*1024*1024: raise ValueError('pdf_page_stream_limit')
        text=page.extract_text() or ''
        if text.strip(): found=True
        excerpt=f'[PDF page {number}]\n'+(text if text.strip() else '[No extractable text on this page]')
        size+=len(excerpt)+2
        if size > MAX_CHARS: raise ValueError('extracted_text_limit')
        parts.append(excerpt)
    if not found: raise ValueError('no_text_ocr_not_supported')
    return '\n\n'.join(parts),{'pages':len(reader.pages),'ocr':False,'format':'pdf'}

@contextmanager
def validated_package(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries=archive.infolist()
        if len(entries)>200 or sum(item.file_size for item in entries)>8*1024*1024: raise ValueError('package_limits')
        names=set()
        for item in entries:
            name=item.filename
            if name in names or len(name)>240 or name.startswith('/') or '\\' in name or ':' in name or '..' in name.split('/'):
                raise ValueError('invalid_package_path')
            names.add(name)
            if item.flag_bits&1 or ((item.external_attr>>16)&0o170000)==0o120000:
                raise ValueError('encrypted_or_linked_entry')
            if item.file_size>2*1024*1024 or (item.file_size and item.file_size/max(1,item.compress_size)>100):
                raise ValueError('entry_expansion_limit')
            if name.lower().endswith('.bin'): raise ValueError('embedded_binary_or_macro_not_supported')
        if '[Content_Types].xml' not in names: raise ValueError('office_package_required')
        yield archive,names


def read_xml(archive,name):
    text=archive.read(name).decode('utf-8')
    if '\0' in text or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper(): raise ValueError('xml_entities_not_supported')
    return ET.fromstring(text)


def extract_docx(raw):
    with validated_package(raw) as (archive,names):
        if 'word/document.xml' not in names: raise ValueError('docx_document_required')
        root=read_xml(archive,'word/document.xml')
    namespace='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    if root.tag != namespace+'document': raise ValueError('invalid_docx_document')
    parts=[]; size=0
    for paragraph in root.iter(namespace+'p'):
        pieces=[]
        for element in paragraph.iter():
            if element.tag==namespace+'t': pieces.append(element.text or '')
            elif element.tag==namespace+'tab': pieces.append('\t')
            elif element.tag in {namespace+'br',namespace+'cr'}: pieces.append('\n')
        value=''.join(pieces)
        size+=len(value)+1
        if size>MAX_CHARS or len(parts)>=5000: raise ValueError('docx_extracted_text_limit')
        parts.append(value)
    content='\n'.join(parts)
    if not content.strip(): raise ValueError('docx_has_no_main_document_text')
    return '[DOCX main document text]\n'+content,{'paragraphs':len(parts),'format':'docx','images_headers_footers_extracted':False}

def extract_xlsx(raw):
    namespace='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    relns='{http://schemas.openxmlformats.org/package/2006/relationships}'
    ridns='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
    with validated_package(raw) as (archive,names):
        if not {'xl/workbook.xml','xl/_rels/workbook.xml.rels'}.issubset(names): raise ValueError('xlsx_workbook_required')
        workbook=read_xml(archive,'xl/workbook.xml')
        if workbook.tag!=namespace+'workbook': raise ValueError('invalid_xlsx_workbook')
        relations=read_xml(archive,'xl/_rels/workbook.xml.rels')
        targets={}
        for relation in relations.findall(relns+'Relationship'):
            if relation.get('TargetMode')=='External': continue
            target=relation.get('Target','')
            path=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            if '..' in path.split('/') or '\\' in path or ':' in path: raise ValueError('invalid_sheet_relationship')
            targets[relation.get('Id')]=path
        strings=[]
        if 'xl/sharedStrings.xml' in names:
            shared=read_xml(archive,'xl/sharedStrings.xml')
            for entry in shared.findall(namespace+'si'):
                value=''.join(item.text or '' for item in entry.iter(namespace+'t'))
                if len(value)>4000 or len(strings)>=100_000: raise ValueError('xlsx_shared_string_limits')
                strings.append(value)
        sheets=workbook.find(namespace+'sheets')
        if sheets is None: raise ValueError('xlsx_sheets_required')
        visible=[sheet for sheet in sheets if sheet.get('state','visible')=='visible']
        if not 1<=len(visible)<=10: raise ValueError('xlsx_visible_sheet_limit_10')
        parts=[];formula_count=0;row_count=0;size=0;cell_count=0
        for sheet in visible:
            name=sheet.get('name','')
            if not name or len(name)>31: raise ValueError('xlsx_sheet_name_limit')
            path=targets.get(sheet.get(ridns))
            if not path or not path.startswith('xl/worksheets/') or path not in names: raise ValueError('xlsx_sheet_relationship_required')
            root=read_xml(archive,path)
            if root.tag!=namespace+'worksheet': raise ValueError('invalid_xlsx_sheet')
            parts.append('[XLSX sheet: '+name+']');size+=len(parts[-1])+1
            data=root.find(namespace+'sheetData')
            if data is None: continue
            cells_seen=set()
            for row in data.findall(namespace+'row'):
                row_count+=1
                if row_count>1000 or len(row)>50: raise ValueError('xlsx_row_column_limit')
                cells=[]
                for cell in row.findall(namespace+'c'):
                    cell_count+=1
                    reference=cell.get('r','');match=re.fullmatch(r'([A-Z]{1,2})([1-9][0-9]{0,3})',reference)
                    if not match or reference in cells_seen: raise ValueError('xlsx_cell_reference_required')
                    cells_seen.add(reference)
                    col=0
                    for letter in match[1]: col=col*26+ord(letter)-64
                    if col>50 or int(match[2])>1000: raise ValueError('xlsx_row_column_limit')
                    value=cell.find(namespace+'v');value=value.text if value is not None and value.text else ''
                    kind=cell.get('t','n')
                    if kind=='s':
                        if not value.isdecimal() or int(value)>=len(strings): raise ValueError('invalid_shared_string')
                        value=strings[int(value)]
                    elif kind=='inlineStr': value=''.join(item.text or '' for item in cell.iter(namespace+'t'))
                    elif kind not in {'n','b','e','str','d'}: raise ValueError('unsupported_xlsx_cell_type')
                    formula=cell.find(namespace+'f')
                    if formula is not None:
                        formula_count+=1
                        value='[Formula not evaluated: '+(formula.text or '')+'; cached value: '+value+']'
                    if len(value)>4000: raise ValueError('xlsx_cell_text_limit')
                    cells.append(reference+'='+value)
                line='\t'.join(cells);size+=len(line)+1
                if size>MAX_CHARS: raise ValueError('xlsx_extracted_text_limit')
                parts.append(line)
        content='\n'.join(parts)
        if cell_count==0: raise ValueError('xlsx_has_no_visible_cells')
        return content,{'format':'xlsx','visible_sheets':len(visible),'hidden_sheets_omitted':len(sheets)-len(visible),
                        'rows':row_count,'formulas_not_evaluated':formula_count,'cached_values_verified':False}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    # Windows parent applies a Job Object before sending any document bytes.
    if os.name != 'nt':
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024))
        resource.setrlimit(resource.RLIMIT_CPU,(5,5))
        resource.setrlimit(resource.RLIMIT_NOFILE,(32,32))
    payload=json.loads(sys.stdin.buffer.read(2*1024*1024+1))
    if payload.get('limits_applied') is not True: raise ValueError('resource_limits_required')
    raw=base64.b64decode(payload['data'],validate=True)
    if not 0<len(raw)<=MAX_BYTES: raise ValueError('binary_document_limit')
    kind=payload.get('kind')
    if kind=='pdf': content,diagnostics=extract_pdf(raw)
    elif kind=='docx': content,diagnostics=extract_docx(raw)
    elif kind=='xlsx': content,diagnostics=extract_xlsx(raw)
    else: raise ValueError('unsupported_document_kind')
    digest=hashlib.sha256(raw).hexdigest()
    content=f'[Extracted local {kind.upper()} source; SHA-256 {digest}]\n'+content
    if len(content)>MAX_CHARS or len(content.encode('utf-8'))>MAX_TEXT_BYTES or '\0' in content:
        raise ValueError('extracted_text_limit')
    print(json.dumps({'content':content,'source_sha256':digest,'diagnostics':diagnostics},ensure_ascii=False))

if __name__=='__main__':
    try: main()
    except Exception:
        print(json.dumps({'error':'document_unreadable_unsupported_or_over_limits'}))
        sys.exit(1)
