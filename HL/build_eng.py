#!/usr/bin/env python3
"""Builds the English edition (HL ENG) from HL.html.

    python3 HL/build_eng.py

Writes HL/HL_ENG.html and HL/HLEngApp.cs. Run it again after every change to HL.html.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'HL.html'), encoding='utf-8').read()
cs = open(os.path.join(HERE, 'HLApp.cs'), encoding='utf-8').read()

# (korean, english) -- applied longest first, as plain substring replacement
T = [
# ---- header / tabs / tools
('<button data-v="day" class="on">일간</button><button data-v="week">주간</button><button data-v="month">월간</button><button data-v="year">연간</button>',
 '<button data-v="day" class="on">Day</button><button data-v="week">Week</button><button data-v="month">Month</button><button data-v="year">Year</button>'),
('title="이전 날 (←)"', 'title="Previous day (←)"'),
('title="다음 날 (→)"', 'title="Next day (→)"'),
('title="클릭: 날짜 선택 · 우클릭: D-DAY 추가"', 'title="Click: pick a date · Right-click: add a D-DAY"'),
('id="today">오늘</button>', 'id="today">Today</button>'),
('title="A4 프린트용 플래너 (세로 · 가로)">🖨 프린트', 'title="Printable A4 planner (portrait / landscape)">🖨 Print'),
('title="화면 조절 (투명도 · 크기 · 배경)">🎛 화면', 'title="Display (size)">🎛 Display'),
('title="소리 조절"', 'title="Sound"'),
('title="전체화면 (F11)">⛶ 전체화면', 'title="Fullscreen (F11)">⛶ Fullscreen'),
('title="데이터를 파일로 저장">백업', 'title="Save your data to a file">Backup'),
('title="백업 파일 불러오기">복원', 'title="Load a backup file">Restore'),
('title="날짜 칸에서 우클릭해도 추가할 수 있어요">＋ 추가', 'title="You can also right-click a date to add one">＋ Add'),
# ---- timetable panel
('<h2>타임테이블</h2>', '<h2>Timetable</h2>'),
('<i class="lp"></i>예정 · 우클릭 드래그', '<i class="lp"></i>Plan · right-drag'),
('<i class="lr"></i>기록 · 좌클릭 드래그', '<i class="lr"></i>Actual · left-drag'),
('예정<b id="sumPlan">0분</b>', 'Plan<b id="sumPlan">0m</b>'),
('기록<b id="sumRec">0분</b>', 'Actual<b id="sumRec">0m</b>'),
('title="과목별 시간 통계">📊 통계', 'title="Time by subject">📊 Stats'),
('title="어떤 과목의 일인가요?"', 'title="Which subject is this for?"'),
('placeholder="예상" maxlength="8" title="예상 시간 (예: 30 · 1:30 · 1h20)"', 'placeholder="Est." maxlength="8" title="Estimated time (e.g. 30 · 1:30 · 1h20)"'),
('placeholder="할 일 입력 후 Enter"', 'placeholder="Type a task, press Enter"'),
('<button type="submit">추가</button>', '<button type="submit">Add</button>'),
('data-ph="이 날의 메모를 자유롭게 적어보세요… (글자를 드래그해서 선택한 뒤 아래 팔레트로 색을 바꿀 수 있어요)"', 'data-ph="Write anything about this day… (select some text, then pick a color below)"'),
('<span id="memoSt">자동 저장돼요</span>', '<span id="memoSt">Saved automatically</span>'),
('title="메모 글자색"', 'title="Text color"'),
# ---- week / month / year headings
('<h2>요일별 계획</h2><span class="muted">요일 이름을 누르면 그날의 일간 플래너로 이동해요</span>', '<h2>Daily plans</h2><span class="muted">Click a weekday name to open that day</span>'),
('<h2>🎯 주간 목표</h2>', '<h2>🎯 Weekly goals</h2>'),
('<h2>📝 이번 주 할 일</h2>', '<h2>📝 This week\'s tasks</h2>'),
('<h2>월간 달력</h2><span class="muted">날짜 → 일간 · 주차 → 주간으로 이동해요</span>', '<h2>Monthly calendar</h2><span class="muted">Click a date → Day · a week → Week</span>'),
('<h2>📌 이달의 계획</h2>', '<h2>📌 Monthly plans</h2>'),
('<h2>연간 계획</h2><span class="muted">달마다 할 일을 짜보세요 · 달 이름을 누르면 월간으로 이동해요</span>', '<h2>Yearly plan</h2><span class="muted">Plan each month · click a month name to open it</span>'),
('id="gTitle">오늘의 달성률</span>', 'id="gTitle">Today\'s progress</span>'),
# ---- popups
('placeholder="무엇을 할까요?"', 'placeholder="What are you working on?"'),
('<option value="rec">기록</option><option value="plan">예정</option>', '<option value="rec">Actual</option><option value="plan">Plan</option>'),
('<button class="rm" id="popRm">삭제</button><button id="popNo">취소</button><button class="ok" id="popOk">저장</button>', '<button class="rm" id="popRm">Delete</button><button id="popNo">Cancel</button><button class="ok" id="popOk">Save</button>'),
('<h3>과목 · 색상 편집</h3><p>이름을 바꾸고 무지개 버튼으로 색을 직접 골라요. 자주 쓰는 색은 팔레트에 저장해 두면 여기에 나타나요. 기록은 진한 색, 예정은 연한 색으로 칠해져요. (과목 단축키: 숫자 1~9)</p>',
 '<h3>Subjects &amp; colors</h3><p>Rename a subject and pick its color with the rainbow button. Colors you save in the palette show up here. Actuals are drawn in the full color, plans in a lighter tint. (Subject shortcuts: keys 1–9)</p>'),
('<button id="subAdd">+ 과목 추가</button><button class="ok" id="subDone">완료</button>', '<button id="subAdd">+ Add subject</button><button class="ok" id="subDone">Done</button>'),
('<div id="dnH">✅ 실제로 한 시간 기록</div>', '<div id="dnH">✅ Log the time you actually spent</div>'),
('<div class="dn-row"><span>과목</span>', '<div class="dn-row"><span>Subject</span>'),
('<div class="dn-row"><span>시간</span>', '<div class="dn-row"><span>Time</span>'),
('<div class="dn-row"><span>걸린 시간</span>', '<div class="dn-row"><span>Duration</span>'),
('<div class="dn-note">저장하면 타임테이블에 기록으로 들어가요.</div>', '<div class="dn-note">Saving adds it to the timetable as an actual block.</div>'),
('<button id="dnNo">취소</button><button id="dnSkip">기록 안 함</button><button class="ok" id="dnOk">저장</button>', '<button id="dnNo">Cancel</button><button id="dnSkip">Don\'t log</button><button class="ok" id="dnOk">Save</button>'),
('<h3 id="stH">📊 통계</h3>', '<h3 id="stH">📊 Stats</h3>'),
('id="stClose">닫기</button>', 'id="stClose">Close</button>'),
('<div id="ddPt">🔥 D-DAY 추가</div>', '<div id="ddPt">🔥 Add D-DAY</div>'),
('placeholder="D-DAY 이름 (예: 중간고사)"', 'placeholder="D-DAY name (e.g. Midterm)"'),
('<button class="rm" id="ddRm">삭제</button><button id="ddNo">취소</button><button class="ok" id="ddOk">저장</button>', '<button class="rm" id="ddRm">Delete</button><button id="ddNo">Cancel</button><button class="ok" id="ddOk">Save</button>'),
('자주 쓰는 색 9칸 · 빈 칸 클릭 = 현재 색 저장 · 색 칸 클릭 = 적용 · 우클릭 = 비우기', '9 favorite colors · click an empty slot = save current color · click a color = apply · right-click = clear'),
('<button id="cpSave">★ 저장</button><button id="cpOk" class="ok">확인</button>', '<button id="cpSave">★ Save</button><button id="cpOk" class="ok">OK</button>'),
('<div class="sp-title">🎛 화면 조절</div>', '<div class="sp-title">🎛 Display</div>'),
('<span>패널 투명도</span>', '<span>Panel transparency</span>'),
('<span>글자·UI 크기</span>', '<span>UI size</span>'),
('<span>배경 밝기</span>', '<span>Backdrop</span>'),
('<span>시작 시 창 최대화</span>', '<span>Start maximized</span>'),
('<button id="vReset">기본값으로</button>', '<button id="vReset">Reset</button>'),
('투명도를 올리면 타임테이블·달력·할 일 패널 뒤로 배경 그림이 더 잘 보여요.', 'Raising the transparency lets the backdrop show through the panels.'),
('<div class="sp-title">🎧 소리 조절</div>', '<div class="sp-title">🎧 Sound</div>'),
('<span>🖱️ 효과음</span>', '<span>🖱️ Effects</span>'),
('<button id="bgmToggle">▶ 재생</button><button id="bgmPick">🎼 BGM 파일 선택</button>', '<button id="bgmToggle">▶ Play</button><button id="bgmPick">🎼 Choose BGM file</button>'),
('<b>🖨 프린트 (A4)</b>', '<b>🖨 Print (A4)</b>'),
('<option value="day">일간</option><option value="week">주간</option><option value="month">월간</option><option value="year">연간</option>', '<option value="day">Day</option><option value="week">Week</option><option value="month">Month</option><option value="year">Year</option>'),
('<option value="p">세로</option><option value="l">가로</option>', '<option value="p">Portrait</option><option value="l">Landscape</option>'),
('<option value="cur">보고 있는 날짜 기준</option><option value="today">오늘 기준</option>', '<option value="cur">Date I\'m viewing</option><option value="today">Today</option>'),
('title="타임테이블 칸 크기 (형광펜으로 칠할 때)"><option value="0">칸 작게</option><option value="1" selected>칸 보통</option><option value="2">칸 크게</option>', 'title="Timetable cell size (for highlighters)"><option value="0">Small cells</option><option value="1" selected>Medium cells</option><option value="2">Large cells</option>'),
('<option value="color">컬러</option><option value="bw">흑백</option>', '<option value="color">Color</option><option value="bw">B&amp;W</option>'),
('🖨 인쇄</button><button class="chip" id="pvClose">닫기</button>', '🖨 Print</button><button class="chip" id="pvClose">Close</button>'),
# ---- JS strings
("const DOW=['일','월','화','수','목','금','토'];", "const DOW=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];\nconst MON=['January','February','March','April','May','June','July','August','September','October','November','December'];\nconst MONS=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];"),
("const fmtDur=m=>{const h=Math.floor(m/60),r=m%60;return h?(r?`${h}시간 ${r}분`:`${h}시간`):`${r}분`};", "const fmtDur=m=>{const h=Math.floor(m/60),r=m%60;return h?(r?`${h}h ${r}m`:`${h}h`):`${r}m`};"),
("const CNAME=['빨강','주황','노랑','연두','초록','청록','하늘','파랑','보라','자홍','분홍','흰색'];", "const CNAME=['Red','Orange','Yellow','Lime','Green','Teal','Sky','Blue','Purple','Magenta','Pink','White'];"),
("const DEF_SUBJ=['국어','수학','영어','과학','사회','기타'];", "const DEF_SUBJ=['Korean','Math','English','Science','History','Other'];"),
("toast('저장에 실패했어요')", "toast('Could not save')"),
("(lay==='plan'?'예정':'기록')+' 수정':(lay==='plan'?'예정':'기록')+' 추가'", "(lay==='plan'?'Plan':'Actual')+' · edit':(lay==='plan'?'Plan':'Actual')+' · add'"),
("toast('시간을 확인해주세요 (예: 09:00 ~ 10:30)')", "toast('Check the times (e.g. 09:00 ~ 10:30)')"),
('<div class="empty">아직 할 일이 없어요<br>위에 입력하고 Enter를 눌러 추가해보세요</div>', '<div class="empty">No tasks yet<br>Type one above and press Enter</div>'),
('placeholder="예상" maxlength="8" title="예상 시간 (예: 30 · 1:30 · 1h20)" value=', 'placeholder="Est." maxlength="8" title="Estimated time (e.g. 30 · 1:30 · 1h20)" value='),
('title="과목">${subOpts', 'title="Subject">${subOpts'),
('data-a="chk" title="완료"', 'data-a="chk" title="Done"'),
('title="실제 ${fmtT(t.rs)} ~ ${fmtT(t.re)}"', 'title="Actual ${fmtT(t.rs)} ~ ${fmtT(t.re)}"'),
('title="저장해 둔 색"', 'title="Saved color"'),
('title="팔레트에서 고르기"', 'title="Pick from the palette"'),
('title="색 없음"', 'title="No color"'),
('data-a="del" title="삭제"', 'data-a="del" title="Delete"'),
("`${d.filter(t=>t.d).length} / ${d.length} 완료`", "`${d.filter(t=>t.d).length} / ${d.length} done`"),
("(?:h|시간|시))?", "(?:h|hr|hrs|hours?))?"),
("(?:m|분)?)?$/", "(?:m|min|mins|minutes?)?)?$/"),
("`⏳ 예상 합계 ${fmtDur(tot)} · 완료한 것 ${fmtDur(dn)} · 실제 기록 ${fmtDur(rec)}`", "`⏳ Estimated ${fmtDur(tot)} · Done ${fmtDur(dn)} · Logged ${fmtDur(rec)}`"),
("'<span class=\"lbl\">과목</span>'", "'<span class=\"lbl\">Subject</span>'"),
("b.title='단축키 '+(i+1)", "b.title='Shortcut '+(i+1)"),
("b.title='과목에 없는 일 (ETC)'", "b.title='Not tied to a subject (ETC)'"),
("g.textContent='🎨 편집'", "g.textContent='🎨 Edit'"),
("inp.placeholder='과목 이름'", "inp.placeholder='Subject name'"),
("cur.title='현재 색'", "cur.title='Current color'"),
("b.title='저장해 둔 색'", "b.title='Saved color'"),
("cp.title='팔레트에서 직접 고르기'", "cp.title='Pick any color'"),
("del.title='삭제'", "del.title='Delete'"),
("toast('과목은 최소 1개가 필요해요')", "toast('You need at least one subject')"),
("name:'새 과목'", "name:'New subject'"),
("`완료 ${done} / 전체 ${total}`", "`${done} / ${total} done`"),
("curKey===today?'오늘의 달성률':'이 날의 달성률'", "curKey===today?'Today\\'s progress':'This day\\'s progress'"),
("!total?'할 일을 추가해보세요':pct===0?'시작이 반이에요':pct<50?'좋은 시작이에요':pct<100?'거의 다 왔어요!':'모두 완료! 🎉'", "!total?'Add a task to get started':pct===0?'Getting started is half the battle':pct<50?'Good start':pct<100?'Almost there!':'All done! 🎉'"),
("toast('자주 쓰는 색에 저장했어요')", "toast('Saved to your favorite colors')"),
("tg.textContent=bgmPlaying?'⏸ 일시정지':'▶ 재생'", "tg.textContent=bgmPlaying?'⏸ Pause':'▶ Play'"),
("loading:'BGM을 불러오는 중…'", "loading:'Loading BGM…'"),
("ready:'Tokyo Daylight — Persona 5 · 처음(0:00)부터 끝까지 계속 반복'", "ready:'Looping from the start to the end'"),
("missing:'BGM 파일이 없어요. 아래 [BGM 파일 선택]으로 mp3를 골라주세요.'", "missing:'No BGM file yet. Use [Choose BGM file] to pick an mp3.'"),
("error:'이 파일은 재생할 수 없어요. 다른 mp3를 골라주세요.'", "error:'This file can\\'t be played. Try another mp3.'"),
("toast('BGM을 저장했어요')", "toast('BGM saved')"),
("toast('BGM 파일을 읽지 못했어요')", "toast('Could not read the BGM file')"),
("m.length+'자'", "m.length+' chars'"),
("v.length+'자'", "v.length+' chars'"),
("$('#memoSt').textContent='자동 저장돼요'", "$('#memoSt').textContent='Saved automatically'"),
("$('#memoSt').textContent='저장 중…'", "$('#memoSt').textContent='Saving…'"),
("$('#memoSt').textContent='저장됨 ✓'", "$('#memoSt').textContent='Saved ✓'"),
("toast('색을 바꿀 글자를 먼저 드래그해서 선택하세요')", "toast('Select the text you want to recolor first')"),
("b.title='저장해 둔 색 · 선택한 글자에 적용'", "b.title='Apply this saved color to the selected text'"),
("cu.title='팔레트에서 색 고르기 · 선택한 글자에 적용'", "cu.title='Pick any color for the selected text'"),
("rs.title='선택한 글자 색 지우기'", "rs.title='Clear the color of the selected text'"),
('<span class="dd-empty">날짜 칸에서 우클릭하면 D-DAY를 추가할 수 있어요</span>', '<span class="dd-empty">Right-click a date to add a D-DAY</span>'),
("edit?'🔥 D-DAY 수정':'🔥 D-DAY 추가'", "edit?'🔥 Edit D-DAY':'🔥 Add D-DAY'"),
("h.textContent='이 날의 D-DAY'", "h.textContent='D-DAYs on this date'"),
("toast('날짜를 골라주세요')", "toast('Pick a date')"),
("const weekLabel=mon=>{const th=addDays(mon,3);return `${th.getMonth()+1}월 ${Math.ceil(th.getDate()/7)}주차`};", "const weekLabel=mon=>{const th=addDays(mon,3);return `${MONS[th.getMonth()]} · week ${Math.ceil(th.getDate()/7)}`};"),
("const fmtMD=d=>`${d.getMonth()+1}월 ${d.getDate()}일`;", "const fmtMD=d=>`${MONS[d.getMonth()]} ${d.getDate()}`;"),
("chk.title='완료'", "chk.title='Done'"),
("x.title='삭제'", "x.title='Delete'"),
("o.ph||'+ 추가'", "o.ph||'+ Add'"),
("names=['월','화','수','목','금','토','일']", "names=['Mon','Tue','Wed','Thu','Fri','Sat','Sun']"),
("head.title='일간 플래너 열기'", "head.title='Open the day planner'"),
("ph:'+ 할 일'", "ph:'+ Task'"),
("ph:'+ 이번 주 목표 (Enter)'", "ph:'+ Weekly goal (Enter)'"),
("ph:'+ 이번 주 할 일 (Enter)'", "ph:'+ This week\\'s task (Enter)'"),
("`${gc.d} / ${gc.t} 완료`", "`${gc.d} / ${gc.t} done`"),
("`${tc.d} / ${tc.t} 완료`", "`${tc.d} / ${tc.t} done`"),
("hd.textContent='주차'", "hd.textContent='Week'"),
("['월','화','수','목','금','토','일'].forEach", "['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].forEach"),
("wc.title='주간 플래너 열기'", "wc.title='Open the week planner'"),
('<span class="g none">계획 없음</span>', '<span class="g none">No plans</span>'),
("`<span class=\"g none\">+${items.length-5}개 더</span>`", "`<span class=\"g none\">+${items.length-5} more</span>`"),
("cell.title='일간 플래너 열기'", "cell.title='Open the day planner'"),
("`<span class=\"more\">+${todos.length-3}개 더</span>`", "`<span class=\"more\">+${todos.length-3} more</span>`"),
("ph:'+ 이달의 계획 (Enter)'", "ph:'+ Monthly plan (Enter)'"),
("`${pc.d} / ${pc.t} 완료`", "`${pc.d} / ${pc.t} done`"),
("head.title='월간 플래너 열기'", "head.title='Open the month planner'"),
("`<b>${m+1}월</b><small>", "`<b>${MON[m]}</b><small>"),
("ph:`+ ${m+1}월 할 일`", "ph:`+ ${MON[m]} task`"),
("title=(cur?'이번 주':'이 주')+'의 달성률';note='주간 목표 + 이번 주 할 일 + 요일별 할 일 기준'", "title=(cur?'This week':'This week')+'\\'s progress';note='Based on weekly goals + weekly tasks + daily tasks'"),
("title=(cur?'이번 달':'이 달')+'의 달성률';note='이달의 계획 + 매일의 할 일 기준'", "title=(cur?'This month':'This month')+'\\'s progress';note='Based on monthly plans + daily tasks'"),
("title=(cur?'올해':'이 해')+'의 달성률';note='월별 계획 기준'", "title=(cur?'This year':'This year')+'\\'s progress';note='Based on the monthly plans'"),
("`완료 ${r.d} / 전체 ${r.t}`", "`${r.d} / ${r.t} done`"),
("!r.t?'계획을 추가해보세요':pct===0?'시작이 반이에요':pct<50?'좋은 출발이에요':pct<100?'거의 다 왔어요!':'모두 달성! 🎉'", "!r.t?'Add a plan to get started':pct===0?'Getting started is half the battle':pct<50?'Good start':pct<100?'Almost there!':'All done! 🎉'"),
("main=`${d.getFullYear()}년 ${d.getMonth()+1}월 ${d.getDate()}일`;", "main=`${MON[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;"),
("tag=diff===0?'오늘':diff===1?'내일':diff===-1?'어제':'';", "tag=diff===0?'Today':diff===1?'Tomorrow':diff===-1?'Yesterday':'';"),
("sub=`${DOW[d.getDay()]}요일`;", "sub=`${DOW[d.getDay()]}`;"),
("main=`${addDays(mon,3).getFullYear()}년 ${weekLabel(mon)}`;", "main=`${weekLabel(mon)} ${addDays(mon,3).getFullYear()}`;"),
("tag=keyOf(mon)===keyOf(monOf(td))?'이번 주':'';", "tag=keyOf(mon)===keyOf(monOf(td))?'This week':'';"),
("main=`${d.getFullYear()}년 ${d.getMonth()+1}월`;", "main=`${MON[d.getMonth()]} ${d.getFullYear()}`;"),
("sub=`${dim(d.getFullYear(),d.getMonth())}일`;", "sub=`${dim(d.getFullYear(),d.getMonth())} days`;"),
("?'이번 달':'';", "?'This month':'';"),
("main=`${d.getFullYear()}년`;sub='12개월 계획';", "main=`${d.getFullYear()}`;sub='12-month plan';"),
("tag=d.getFullYear()===td.getFullYear()?'올해':'';", "tag=d.getFullYear()===td.getFullYear()?'This year':'';"),
("{day:'날',week:'주',month:'달',year:'해'}[view]", "{day:'day',week:'week',month:'month',year:'year'}[view]"),
("$('#prev').title='이전 '+u+' (←)';$('#next').title='다음 '+u+' (→)';", "$('#prev').title='Previous '+u+' (←)';$('#next').title='Next '+u+' (→)';"),
("{day:'오늘',week:'이번 주',month:'이번 달',year:'올해'}[view]", "{day:'Today',week:'This week',month:'This month',year:'This year'}[view]"),
("'⛶ 창모드':'⛶ 전체화면'", "'⛶ Windowed':'⛶ Fullscreen'"),
("toast('백업 파일을 저장했어요')", "toast('Backup file saved')"),
("confirm('현재 데이터를 백업 파일로 덮어쓸까요?')", "confirm('Replace your current data with this backup?')"),
("toast('복원했어요')", "toast('Restored')"),
("toast('올바른 백업 파일이 아니에요')", "toast('This is not a valid backup file')"),
("'<table class=\"stt\"><tr><th>과목</th><th>예정</th><th>기록</th><th></th><th>예상</th><th>실제</th></tr>'", "'<table class=\"stt\"><tr><th>Subject</th><th>Plan</th><th>Actual</th><th></th><th>Est.</th><th>Spent</th></tr>'"),
("<tr class=\"tot\"><td>합계</td><td>${f(tot.plan)}</td><td>${f(tot.rec)}</td><td></td>", "<tr class=\"tot\"><td>Total</td><td>${f(tot.plan)}</td><td>${f(tot.rec)}</td><td></td>"),
("`<p class=\"stn\">예상한 일 ${dn.length}개를 마쳤고, 예상보다 <b>${diff>0?fmtEst(diff)+' 더':diff<0?fmtEst(-diff)+' 덜':'딱 맞게'}</b> 걸렸어요.</p>`", "`<p class=\"stn\">You finished ${dn.length} estimated task${dn.length>1?'s':''} and took <b>${diff>0?fmtEst(diff)+' longer':diff<0?fmtEst(-diff)+' less':'exactly as long'}</b> than estimated.</p>`"),
("'<p class=\"stn\">ETC는 과목에 속하지 않는 일이에요. 할 일에서 과목을 ETC로 두면 여기에 모여요.</p>'", "'<p class=\"stn\">ETC is for tasks that don\\'t belong to a subject. Leave a task on ETC and it is counted here.</p>'"),
("`📊 ${dt.getMonth()+1}월 ${dt.getDate()}일 통계`", "`📊 ${MONS[dt.getMonth()]} ${dt.getDate()} · Stats`"),
("const DN=['일','월','화','수','목','금','토'];", "const DN=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];"),
("`<div class=\"ln mu\">+${a.length-shown}개 더</div>`", "`<div class=\"ln mu\">+${a.length-shown} more</div>`"),
("'<table class=\"st\"><tr><th></th><th>예정</th><th>기록</th><th>예상</th><th>실제</th></tr>'", "'<table class=\"st\"><tr><th></th><th>Plan</th><th>Actual</th><th>Est.</th><th>Spent</th></tr>'"),
("<tr class=\"tot\"><td>합계</td><td>${f(tot.plan)}</td><td>${f(tot.rec)}</td><td>${f(tot.est)}</td>", "<tr class=\"tot\"><td>Total</td><td>${f(tot.plan)}</td><td>${f(tot.rec)}</td><td>${f(tot.est)}</td>"),
# print sheets
("pgHead('일간 플래너',`${dt.getFullYear()}년 ${dt.getMonth()+1}월 ${dt.getDate()}일`,`${DN[dt.getDay()]}요일`", "pgHead('Daily planner',`${MON[dt.getMonth()]} ${dt.getDate()}, ${dt.getFullYear()}`,`${DN[dt.getDay()]}`"),
('<span class="ach">달성 <i class="wbx big"></i> %</span>', '<span class="ach">Done <i class="wbx big"></i> %</span>'),
("pgBox('🎯 이번 주 목표'", "pgBox('🎯 Weekly goals'"),
("pgBox('📌 이달의 계획'", "pgBox('📌 Monthly plans'"),
("pgBox('✅ 할 일'+(estT?` · 예상 합계 ${fmtDur(estT)}`:'')+' <small style=\"font-weight:400;opacity:.8\">(오른쪽 빈칸 = 걸린 시간)</small>'", "pgBox('✅ Tasks'+(estT?` · est. total ${fmtDur(estT)}`:'')+' <small style=\"font-weight:400;opacity:.8\">(right box = time spent)</small>'"),
("pgBox('📝 메모'", "pgBox('📝 Notes'"),
("`칸 크기: 가로 ${tz.colMm.toFixed(1)}mm × 세로 ${tz.rowMm}mm`", "`Cell size: ${tz.colMm.toFixed(1)}mm wide × ${tz.rowMm}mm tall`"),
("pgHead('주간 계획표',`${addDays(mon,3).getFullYear()}년 ${weekLabel(mon)}`", "pgHead('Weekly planner',`${weekLabel(mon)} ${addDays(mon,3).getFullYear()}`"),
("pgBox('🎯 주간 목표'", "pgBox('🎯 Weekly goals'"),
("pgBox('📝 이번 주 할 일'", "pgBox('📝 This week\\'s tasks'"),
("pgHead('월간 계획표',`${y}년 ${m+1}월`,`${n}일`", "pgHead('Monthly planner',`${MON[m]} ${y}`,`${n} days`"),
("let g='<div class=\"mh\">주차</div>'+['월','화','수','목','금','토','일']", "let g='<div class=\"mh\">Week</div>'+['Mon','Tue','Wed','Thu','Fri','Sat','Sun']"),
("`<span class=\"mu\">+${its.length-6}개 더</span>`", "`<span class=\"mu\">+${its.length-6} more</span>`"),
("pgBox('📌 이달의 계획',pgLines(mo?mo.plans:[],land?18:7),'mplan')", "pgBox('📌 Monthly plans',pgLines(mo?mo.plans:[],land?18:7),'mplan')"),
("pgHead('연간 계획표',`${y}년`,'12개월 계획'", "pgHead('Yearly planner',`${y}`,'12-month plan'"),
("(${x.date.slice(8)}일)", "(${MONS[+x.date.slice(5,7)-1]} ${+x.date.slice(8)})"),
("`<div class=\"yc\"><div class=\"ych\"><b>${m+1}월</b>", "`<div class=\"yc\"><div class=\"ych\"><b>${MON[m]}</b>"),
("<title>HL</title>", "<title>HL ENG</title>"),
('<html lang="ko">', '<html lang="en">'),
]

out = src
for ko, en in sorted(T, key=lambda p: -len(p[0])):
    if ko not in out:
        print('!! not found:', ko[:90])
        continue
    out = out.replace(ko, en)

# English edition: tighter header so the labels fit on one row
ENG_CSS = '.chip{padding:6px 10px;font-size:13.5px}.tabs button{padding:7px 14px}.datebox{min-width:0}.top{gap:8px 10px}\n'
out = out.replace('</style>\n</head>', ENG_CSS + '</style>\n</head>', 1)
out = out.replace('<em class="beta">ver ', '<em class="beta">ENG ', 1)

# ---- report anything still Korean (outside JS/CSS comments)
left = []
for i, l in enumerate(out.split('\n'), 1):
    if len(l) > 20000:
        continue
    l2 = re.sub(r'//.*$', '', l)
    l2 = re.sub(r'/\*.*?\*/', '', l2)
    if re.search('[가-힣]', l2):
        left.append((i, l.strip()[:220]))
for i, l in left:
    print('KO left', i, l)

open(os.path.join(HERE, 'HL_ENG.html'), 'w', encoding='utf-8').write(out)

# ---- Windows host: separate app / data / mutex / title
c = cs
c = c.replace('HL.HeeseopLife.SingleInstance', 'HL.ENG.SingleInstance')
c = c.replace('Text = "HL";', 'Text = "HL ENG";')
c = c.replace('GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Dp")', 'GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "HLEng")')
c = c.replace('Path.Combine(dir, "HL.html")', 'Path.Combine(dir, "HL_ENG.html")')
c = c.replace('GetManifestResourceStream("HL.html")', 'GetManifestResourceStream("HL_ENG.html")')
c = c.replace('https://dp.local/HL.html', 'https://dp.local/HL_ENG.html')
open(os.path.join(HERE, 'HLEngApp.cs'), 'w', encoding='utf-8').write(c)
print('built HL_ENG.html', len(out) // 1024, 'KB;', len(left), 'lines still contain Korean')
