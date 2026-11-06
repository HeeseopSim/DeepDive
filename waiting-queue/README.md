# QR 대기표 (파이썬, 외부 모듈 없음)

병원 대기표처럼 동작: 손님이 QR을 폰 카메라로 찍어 이름/인원을 등록 → 번호 발급.
직원이 **K 키**를 누르면 맨 위 손님이 삭제되고 다음 사람이 맨 위로 올라옴.

## 실행
```
python queue_server.py
```
- 브라우저가 자동으로 열림 (관리 화면은 이 PC의 `http://localhost:3000` 에서만)
- 시작하면 무료 Cloudflare 터널로 인터넷 주소를 만들어 QR에 넣음 → 같은 Wi-Fi 아니어도 접속
  (처음 한 번 `cloudflared.exe` 자동 다운로드 여부를 묻습니다. `NO_TUNNEL=1` 이면 터널 없이 실행)
- 환경변수: `PORT`, `PUBLIC_URL`, `NO_TUNNEL`, `NO_BROWSER`
- 소켓으로 직접 구현한 HTTP 서버 + 내장 QR 생성기 (pip 설치 불필요)

## 보안
관리 화면/대기 명단/완료(K)는 서버 PC에서만 사용 가능. 손님은 등록/내 상태 확인/내 대기 취소만 가능.

> `app.py`, `waiting_queue.py`, `public/` 은 초기 버전(http.server + segno)입니다.

## PC 서버 + 모바일 앱 (TCP 소켓 통신)
- PC: `python queue_board_pc.py` → 소켓 서버(포트 9000) + 대기표 화면. 위쪽의 `📡 IP:포트`가 서버 주소.
  K: 다음 손님 호출 · N: 수동 추가 · F11: 전체화면 · 목록 항목 클릭: 삭제. 화면 아래에 모바일 접속 로그.
- 모바일: `dist/Daegi-mobile.apk` → 서버 주소(IP:포트) 입력 또는 QR 스캔으로 연결 → 대기 현황/등록/내 순번.
  앱 안에 서버 연결용 QR(`daegi://IP:포트`)이 표시됨.
- 통신: 한 줄 JSON (hello / board / join / status / cancel).
