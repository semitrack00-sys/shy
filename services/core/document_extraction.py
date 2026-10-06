"""Bounded fixed local PDF/DOCX extraction, isolated from the web process."""
from __future__ import annotations
import base64
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import BoundedSemaphore
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

_slots=BoundedSemaphore(2)
MAX_BINARY_BYTES=1024*1024

class ExtractRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    kind:Literal['pdf','docx','xlsx']
    data:str=Field(min_length=1,max_length=1_398_104)
    confirmed:Literal[True]
    @field_validator('confirmed',mode='before')
    @classmethod
    def confirmation(cls,value):
        if value is not True:raise ValueError('explicit_boolean_confirmation_required')
        return value
    @field_validator('data')
    @classmethod
    def binary_size(cls,value):
        try: raw=base64.b64decode(value,validate=True)
        except Exception: raise ValueError('valid_base64_required') from None
        if not 0<len(raw)<=MAX_BINARY_BYTES: raise ValueError('binary_document_limit_1_mib')
        return value


def _windows_job(process):
    # Layout follows Win32 JOBOBJECT_EXTENDED_LIMIT_INFORMATION. The child waits
    # on stdin; assignment succeeds before the parent transfers document bytes.
    from ctypes import wintypes
    class Basic(ctypes.Structure):
        _fields_=[('PerProcessUserTimeLimit',ctypes.c_longlong),('PerJobUserTimeLimit',ctypes.c_longlong),
                  ('LimitFlags',wintypes.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),
                  ('MaximumWorkingSetSize',ctypes.c_size_t),('ActiveProcessLimit',wintypes.DWORD),
                  ('Affinity',ctypes.c_size_t),('PriorityClass',wintypes.DWORD),('SchedulingClass',wintypes.DWORD)]
    class IO(ctypes.Structure):
        _fields_=[(name,ctypes.c_ulonglong) for name in ['ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount']]
    class Extended(ctypes.Structure):
        _fields_=[('BasicLimitInformation',Basic),('IoInfo',IO),('ProcessMemoryLimit',ctypes.c_size_t),
                  ('JobMemoryLimit',ctypes.c_size_t),('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];kernel.CreateJobObjectW.restype=wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD];kernel.SetInformationJobObject.restype=wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE];kernel.AssignProcessToJobObject.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
    handle=kernel.CreateJobObjectW(None,None)
    if not handle: raise RuntimeError('worker_limits_unavailable')
    try:
        limits=Extended();limits.BasicLimitInformation.LimitFlags=0x100|0x2|0x2000
        limits.BasicLimitInformation.PerProcessUserTimeLimit=5*10_000_000
        limits.ProcessMemoryLimit=256*1024*1024
        if not kernel.SetInformationJobObject(handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
            raise RuntimeError('worker_limits_unavailable')
        if not kernel.AssignProcessToJobObject(handle,wintypes.HANDLE(int(process._handle))):
            raise RuntimeError('worker_limits_unavailable')
    except Exception:
        kernel.CloseHandle(handle);raise
    return lambda: kernel.CloseHandle(handle)


def extract_selected(request:ExtractRequest):
    if not _slots.acquire(blocking=False):raise HTTPException(429,'document_extraction_busy')
    process=None;close_job=None
    try:
        process=subprocess.Popen([sys.executable,'-I',str(Path(__file__).with_name('document_worker.py'))],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,shell=False,
            close_fds=True,env={key:value for key,value in os.environ.items() if key.upper() in {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','LANG','LC_ALL'}})
        if os.name=='nt':close_job=_windows_job(process)
        payload=json.dumps({'kind':request.kind,'data':request.data,'limits_applied':True}).encode()
        try: output,_=process.communicate(payload,timeout=10)
        except subprocess.TimeoutExpired:
            process.kill();process.communicate();raise HTTPException(422,'document_extraction_time_limit') from None
        if process.returncode!=0 or len(output)>1024*1024:raise HTTPException(422,'document_unreadable_unsupported_or_over_limits')
        result=json.loads(output)
        content=result.get('content')
        if not isinstance(content,str) or not content.strip() or len(content)>100_000 or len(content.encode('utf-8'))>256*1024:
            raise HTTPException(422,'invalid_extracted_text')
        return {**result,'kind':'text','binary_stored':False,'worker_limits':{'memory_bytes':256*1024*1024,'cpu_seconds':5,'wall_seconds':10,
                'platform':'windows_job' if os.name=='nt' else 'unix_rlimit'}}
    except HTTPException:raise
    except Exception:raise HTTPException(503,'document_extraction_unavailable') from None
    finally:
        if process is not None and process.poll() is None:
            process.kill();process.communicate()
        if close_job is not None:close_job()
        _slots.release()
