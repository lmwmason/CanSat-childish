# KAIST 통신 규격 조사 근거

구현에 반영된 통신 규격과 지원 범위는 [PROTOCOL.md](../../kaist_ground_station/PROTOCOL.md)를 참고한다. 이 폴더는 그 근거 자료를 보관한다.

| 파일 | 역할 |
| --- | --- |
| `온라인교육자료_*.txt` | 사용자 제공 2026 KAIST 교육 PDF 7개의 텍스트 추출본 |
| [source_hashes.json](source_hashes.json) | 조사에 사용한 PDF·배포 ZIP의 SHA-256과 당시 원본 경로 |
| [exe_evidence.json](exe_evidence.json) | 배포 지상국 EXE 해시·섹션·프로토콜 분석 위치 |
| [reference_disassembly.txt](reference_disassembly.txt) | Windows 지상국 EXE의 정적 디스어셈블 결과 |

원본 PDF는 조사 당시 `/home/airhood/Downloads/kaist_cansat_docs/`, 배포 ZIP은 `/home/airhood/Downloads/`에서 읽었다. 원본 경로는 출처 기록이며 이 저장소에서 파일이 존재한다는 보장은 아니다. 배포 페이지: https://cansat.kaist.ac.kr/doc/ko/selectDoc.do?docSeq=10460&menuSeq=3458&bbsSeq=143

EXE는 실행하지 않고 분석했다. 재조사 도구는 [inspect_reference.py](../../kaist_ground_station/tools/inspect_reference.py)이며, 분석 근거와 실제 하드웨어 검증 결과는 구분한다.
