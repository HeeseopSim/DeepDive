package com.deepdive.waitingqueue

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.Vibrator
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import org.json.JSONObject
import java.util.concurrent.Executors

/**
 * 대기표 모바일 앱: PC 서버(queue_board_pc.py)의 "서버 주소(IP:포트)"에 연결해서
 * 같은 대기 현황을 보고, 대기를 등록하고, 내 순번을 확인한다. (웹뷰 없이 앱 화면으로 직접 그림)
 */
class MainActivity : Activity() {
    private val prefs by lazy { getSharedPreferences("cfg", Context.MODE_PRIVATE) }
    private val io = Executors.newCachedThreadPool()
    private val handler = Handler(Looper.getMainLooper())
    private var base: String? = null
    private var notifiedTurn = false

    private val BG = Color.parseColor("#0b1220")
    private val PANEL = Color.parseColor("#111b30")
    private val GREEN = Color.parseColor("#16a34a")
    private val GRAY = Color.parseColor("#1e293b")
    private val MUTED = Color.parseColor("#94a3b8")
    private val BLUE = Color.parseColor("#60a5fa")
    private val AMBER = Color.parseColor("#fbbf24")

    // 공통
    private lateinit var addrLabel: TextView
    private lateinit var connNote: TextView
    private lateinit var setupView: LinearLayout
    private lateinit var mainView: ScrollView
    // 연결 화면
    private lateinit var addrInput: EditText
    private lateinit var setupMsg: TextView
    // 대기 현황
    private lateinit var nowBg: GradientDrawable
    private lateinit var nowNum: TextView
    private lateinit var nowWho: TextView
    private lateinit var listBox: LinearLayout
    private lateinit var countView: TextView
    // 내 대기표 / 등록
    private lateinit var ticketCard: LinearLayout
    private lateinit var ticketBg: GradientDrawable
    private lateinit var ticketNum: TextView
    private lateinit var ticketInfo: TextView
    private lateinit var regCard: LinearLayout
    private lateinit var nameInput: EditText
    private lateinit var sizeInput: EditText
    private lateinit var regMsg: TextView

    private val ticker = object : Runnable {
        override fun run() {
            poll()
            handler.postDelayed(this, 2500)
        }
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
    private fun lp(w: Int, h: Int, weight: Float = 0f, top: Int = 0, left: Int = 0) =
        LinearLayout.LayoutParams(w, h, weight).apply { topMargin = dp(top); leftMargin = dp(left) }

    private fun tv(text: String, sp: Float, color: Int, bold: Boolean = false, center: Boolean = false) =
        TextView(this).apply {
            this.text = text
            textSize = sp
            setTextColor(color)
            if (bold) setTypeface(typeface, Typeface.BOLD)
            if (center) gravity = Gravity.CENTER
        }

    private fun round(color: Int, r: Int = 18) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = dp(r).toFloat()
    }

    private fun card(color: Int = PANEL) = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        background = round(color)
        setPadding(dp(16), dp(14), dp(16), dp(14))
    }

    private fun input(hint: String) = EditText(this).apply {
        this.hint = hint
        setHintTextColor(Color.GRAY)
        setTextColor(Color.WHITE)
        setSingleLine()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(buildUi())
        val saved = prefs.getString("server", null)?.let { normalize(it) }
        if (saved != null) showMain(saved) else showSetup(null)
    }

    // ---------------- 화면 구성 ----------------
    private fun buildUi(): View {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(BG)
        }
        // 상단 바
        val head = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(14), dp(8), dp(8), dp(8))
            setBackgroundColor(PANEL)
        }
        val titles = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        titles.addView(tv("🏥 대기표", 20f, Color.WHITE, true))
        addrLabel = tv("", 13f, AMBER).apply { setTextIsSelectable(true) }
        titles.addView(addrLabel)
        head.addView(titles, lp(0, WRAP_CONTENT, 1f))
        head.addView(Button(this).apply {
            text = "서버 변경"
            setOnClickListener { showSetup(null) }
        })
        root.addView(head, lp(MATCH_PARENT, WRAP_CONTENT))
        connNote = tv("", 13f, Color.parseColor("#fca5a5")).apply { setPadding(dp(14), dp(4), dp(14), dp(4)) }
        root.addView(connNote, lp(MATCH_PARENT, WRAP_CONTENT))

        // --- 연결 화면 ---
        setupView = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(20), dp(20), dp(20))
            visibility = View.GONE
        }
        setupView.addView(tv("PC 프로그램 화면에 표시된\n서버 주소(IP:포트)를 입력하거나 QR을 스캔하세요.", 16f, Color.WHITE))
        setupView.addView(Button(this).apply {
            text = "QR 스캔으로 연결"
            setOnClickListener { scan() }
        }, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 18))
        addrInput = input("예: 192.168.0.10:9000").apply {
            imeOptions = EditorInfo.IME_ACTION_GO
            setOnEditorActionListener { _, _, _ -> tryConnect(text.toString()); true }
        }
        setupView.addView(addrInput, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 14))
        setupView.addView(Button(this).apply {
            text = "연결"
            setOnClickListener { tryConnect(addrInput.text.toString()) }
        }, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 6))
        setupMsg = tv("", 14f, AMBER)
        setupView.addView(setupMsg, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 14))
        setupView.addView(tv("※ 폰과 PC가 같은 Wi-Fi(또는 PC의 핫스팟)에 연결돼 있어야 하고, 입력한 IP가 PC 화면의 주소와 같아야 합니다.", 12f, MUTED),
            lp(MATCH_PARENT, WRAP_CONTENT, 0f, 10))
        root.addView(setupView, lp(MATCH_PARENT, 0, 1f))

        // --- 메인 화면 ---
        val body = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12), dp(12), dp(12), dp(12))
        }
        // 현재 호출
        nowBg = round(GREEN, 22)
        val now = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = nowBg
            setPadding(dp(14), dp(12), dp(14), dp(12))
        }
        now.addView(tv("현재 호출", 15f, Color.WHITE, false, true))
        nowNum = tv("-", 64f, Color.WHITE, true, true)
        now.addView(nowNum)
        nowWho = tv("", 20f, Color.WHITE, true, true)
        now.addView(nowWho)
        body.addView(now, lp(MATCH_PARENT, WRAP_CONTENT))
        // 다음 순서
        val next = card()
        next.addView(tv("다음 순서", 14f, MUTED))
        listBox = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        next.addView(listBox, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 4))
        countView = tv("", 14f, MUTED)
        next.addView(countView, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 6))
        body.addView(next, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 10))
        // 내 대기표
        ticketBg = round(Color.parseColor("#1d4ed8"), 18)
        ticketCard = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = ticketBg
            setPadding(dp(16), dp(14), dp(16), dp(14))
            visibility = View.GONE
        }
        ticketCard.addView(tv("내 대기표", 14f, Color.WHITE, false, true))
        ticketNum = tv("", 52f, Color.WHITE, true, true)
        ticketCard.addView(ticketNum)
        ticketInfo = tv("", 18f, Color.WHITE, true, true)
        ticketCard.addView(ticketInfo)
        ticketCard.addView(Button(this).apply {
            text = "대기 취소"
            setOnClickListener { confirmCancel() }
        }, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 10))
        body.addView(ticketCard, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 10))
        // 등록
        regCard = card()
        regCard.addView(tv("대기 등록", 18f, Color.WHITE, true))
        nameInput = input("이름")
        regCard.addView(nameInput, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 6))
        sizeInput = input("인원").apply {
            inputType = InputType.TYPE_CLASS_NUMBER
            setText("1")
        }
        regCard.addView(sizeInput, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 4))
        regCard.addView(Button(this).apply {
            text = "대기표 받기"
            textSize = 18f
            setOnClickListener { register() }
        }, lp(MATCH_PARENT, dp(56), 0f, 10))
        regMsg = tv("", 14f, AMBER)
        regCard.addView(regMsg, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 6))
        body.addView(regCard, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 10))

        mainView = ScrollView(this).apply {
            addView(body)
            visibility = View.GONE
        }
        root.addView(mainView, lp(MATCH_PARENT, 0, 1f))
        return root
    }

    // ---------------- 화면 전환 ----------------
    private fun showSetup(message: String?) {
        handler.removeCallbacks(ticker)
        mainView.visibility = View.GONE
        setupView.visibility = View.VISIBLE
        connNote.text = ""
        addrInput.setText(prefs.getString("server", "") ?: "")
        setupMsg.text = message ?: ""
    }

    private fun showMain(b: String) {
        base = b
        notifiedTurn = false
        setupView.visibility = View.GONE
        mainView.visibility = View.VISIBLE
        addrLabel.text = "서버 $b"
        handler.removeCallbacks(ticker)
        handler.post(ticker)
    }

    override fun onResume() {
        super.onResume()
        if (base != null && mainView.visibility == View.VISIBLE) {
            handler.removeCallbacks(ticker)
            handler.post(ticker)
        }
    }

    override fun onPause() {
        handler.removeCallbacks(ticker)
        super.onPause()
    }

    // ---------------- 서버 연결 (TCP 소켓) ----------------
    private val defaultPort = 9000

    /** "192.168.0.10:9000", "daegi://192.168.0.10:9000" 등을 "host:port" 로 정리. */
    private fun normalize(raw: String): String? {
        var s = raw.trim()
        if (s.isEmpty()) return null
        s = s.substringAfter("://").substringBefore("/").trim()
        if (s.isEmpty()) return null
        val host = s.substringBefore(":")
        val port = if (s.contains(":")) s.substringAfter(":").toIntOrNull() else defaultPort
        if (host.isEmpty() || port == null || port !in 1..65535) return null
        return "$host:$port"
    }

    private fun call(b: String, req: JSONObject): JSONObject =
        Sock.call(b.substringBefore(":"), b.substringAfter(":").toInt(), req)

    private fun tryConnect(raw: String) {
        val b = normalize(raw)
        if (b == null) {
            setupMsg.text = "주소를 확인해 주세요. 예: 192.168.0.10:9000"
            return
        }
        setupMsg.text = "연결 확인 중… ($b)"
        io.execute {
            try {
                val r = call(b, JSONObject().put("cmd", "hello"))
                if (r.optBoolean("ok") && r.optString("app") == "waiting-queue") {
                    runOnUiThread {
                        prefs.edit().putString("server", b).apply()
                        showMain(b)
                    }
                } else {
                    runOnUiThread { setupMsg.text = "이 주소는 대기표 서버가 아닙니다. PC 화면의 주소(IP:포트)와 같은지 확인하세요." }
                }
            } catch (e: Exception) {
                runOnUiThread {
                    setupMsg.text = "서버에 연결하지 못했습니다 (${e.javaClass.simpleName}: ${e.message}).\n" +
                        "① PC에서 프로그램이 켜져 있는지 ② 폰과 PC가 같은 Wi-Fi인지 ③ 입력한 IP:포트가 PC 화면의 주소와 같은지 확인해 주세요."
                }
            }
        }
    }

    private fun scan() {
        try {
            GmsBarcodeScanning.getClient(this).startScan()
                .addOnSuccessListener { b ->
                    val raw = b.rawValue
                    if (raw != null) {
                        addrInput.setText(raw.substringAfter("://"))
                        tryConnect(raw)
                    } else {
                        setupMsg.text = "QR에서 주소를 읽지 못했습니다."
                    }
                }
                .addOnFailureListener { e ->
                    setupMsg.text = "QR 스캔을 사용할 수 없습니다 (${e.message}). 주소를 직접 입력해 주세요."
                }
        } catch (e: Exception) {
            setupMsg.text = "QR 스캔을 사용할 수 없습니다. 주소를 직접 입력해 주세요."
        }
    }

    // ---------------- 실시간 갱신 ----------------
    private fun poll() {
        val b = base ?: return
        io.execute {
            try {
                val board = call(b, JSONObject().put("cmd", "board"))
                if (!board.optBoolean("ok")) throw RuntimeException(board.optString("error", "응답 오류"))
                val tid = prefs.getInt("ticketId", 0)
                val st = if (tid > 0) call(b, JSONObject().put("cmd", "status").put("id", tid)) else null
                runOnUiThread {
                    connNote.text = ""
                    showBoard(board)
                    showTicket(st)
                }
            } catch (e: Exception) {
                runOnUiThread {
                    connNote.text = "⚠ 서버와 연결이 끊겼습니다 (${e.javaClass.simpleName}) — PC와 같은 네트워크인지 확인하세요"
                }
            }
        }
    }

    private fun showBoard(board: JSONObject) {
        val cur = board.optJSONObject("current")
        if (cur == null) {
            nowBg.setColor(GRAY)
            nowNum.text = "대기 없음"
            nowNum.textSize = 30f
            nowWho.text = ""
        } else {
            nowBg.setColor(GREEN)
            nowNum.text = "${cur.optInt("id")}번"
            nowNum.textSize = 64f
            nowWho.text = "${cur.optString("name")} 님 · ${cur.optInt("size")}명"
        }
        listBox.removeAllViews()
        val next = board.optJSONArray("next")
        val n = next?.length() ?: 0
        for (i in 0 until n) {
            val o = next!!.getJSONObject(i)
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                setPadding(0, dp(5), 0, dp(5))
            }
            row.addView(tv("${o.optInt("id")}번", 20f, BLUE, true), lp(dp(72), WRAP_CONTENT))
            row.addView(tv(o.optString("name"), 18f, Color.WHITE), lp(0, WRAP_CONTENT, 1f))
            row.addView(tv("${o.optInt("size")}명", 16f, MUTED))
            listBox.addView(row, lp(MATCH_PARENT, WRAP_CONTENT))
        }
        val more = board.optInt("more", 0)
        val total = board.optInt("count", 0)
        countView.text = (if (total <= 1) "다음 대기가 없습니다" else if (more > 0) "외 ${more}팀 대기 중" else "") +
            "\n대기 ${total}팀 · ${board.optInt("people", 0)}명"
    }

    private fun showTicket(st: JSONObject?) {
        val tid = prefs.getInt("ticketId", 0)
        if (tid == 0) {
            ticketCard.visibility = View.GONE
            regCard.visibility = View.VISIBLE
            return
        }
        if (st == null) return
        if (st.optBoolean("waiting")) {
            val pos = st.optInt("position")
            ticketCard.visibility = View.VISIBLE
            regCard.visibility = View.GONE
            ticketNum.text = "${tid}번"
            if (pos == 1) {
                ticketBg.setColor(GREEN)
                ticketInfo.text = "🔔 곧 입장 차례입니다!"
                if (!notifiedTurn) {
                    notifiedTurn = true
                    try {
                        @Suppress("DEPRECATION")
                        (getSystemService(Context.VIBRATOR_SERVICE) as Vibrator).vibrate(600)
                    } catch (e: Exception) { /* 진동 불가 기기는 무시 */ }
                }
            } else {
                ticketBg.setColor(Color.parseColor("#1d4ed8"))
                ticketInfo.text = "내 앞 ${st.optInt("teamsAhead")}팀 (${st.optInt("peopleAhead")}명)"
            }
        } else {
            // 호출되었거나 취소된 대기표
            prefs.edit().remove("ticketId").remove("ticketToken").apply()
            notifiedTurn = false
            ticketCard.visibility = View.GONE
            regCard.visibility = View.VISIBLE
            regMsg.text = "대기표 ${tid}번이 호출되었거나 취소되었습니다."
        }
    }

    // ---------------- 등록 / 취소 ----------------
    private fun register() {
        val b = base ?: return
        val name = nameInput.text.toString()
        val size = sizeInput.text.toString().trim().toIntOrNull() ?: 0
        regMsg.text = "등록 중…"
        io.execute {
            try {
                val json = call(b, JSONObject().put("cmd", "join").put("name", name).put("size", size))
                runOnUiThread {
                    if (json.optBoolean("ok")) {
                        prefs.edit().putInt("ticketId", json.optInt("id")).putString("ticketToken", json.optString("token")).apply()
                        notifiedTurn = false
                        regMsg.text = ""
                        nameInput.setText("")
                        poll()
                    } else {
                        regMsg.text = json.optString("error", "등록하지 못했습니다")
                    }
                }
            } catch (e: Exception) {
                runOnUiThread { regMsg.text = "서버에 연결하지 못했습니다 (${e.javaClass.simpleName})" }
            }
        }
    }

    private fun confirmCancel() {
        AlertDialog.Builder(this)
            .setTitle("대기 취소")
            .setMessage("대기를 취소할까요?")
            .setPositiveButton("취소하기") { _, _ -> cancel() }
            .setNegativeButton("닫기", null)
            .show()
    }

    private fun cancel() {
        val b = base ?: return
        val id = prefs.getInt("ticketId", 0)
        val tok = prefs.getString("ticketToken", "") ?: ""
        io.execute {
            try {
                call(b, JSONObject().put("cmd", "cancel").put("id", id).put("token", tok))
            } catch (e: Exception) { /* 다음 갱신에서 상태 확인 */ }
            runOnUiThread {
                prefs.edit().remove("ticketId").remove("ticketToken").apply()
                notifiedTurn = false
                poll()
            }
        }
    }

    override fun onDestroy() {
        handler.removeCallbacks(ticker)
        io.shutdownNow()
        super.onDestroy()
    }
}
