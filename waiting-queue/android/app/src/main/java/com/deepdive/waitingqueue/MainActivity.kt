package com.deepdive.waitingqueue

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.res.Configuration
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.text.TextUtils
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import org.json.JSONObject
import java.util.concurrent.Executors

/**
 * 대기표 모바일 앱: PC 서버(queue_board_pc.py)에 소켓으로 연결해서
 * 왼쪽에 대기표, 오른쪽에 서버 연결 QR 을 한 화면에 띄운다. (화면 크기에 맞춰 자동 조절, 웹뷰 없음)
 */
class MainActivity : Activity() {
    private val prefs by lazy { getSharedPreferences("cfg", Context.MODE_PRIVATE) }
    private val io = Executors.newCachedThreadPool()
    private val handler = Handler(Looper.getMainLooper())
    private var base: String? = null
    private var lastBoard: JSONObject? = null
    private var scale = 1f
    private var maxRows = 5

    private val BG = Color.parseColor("#0b1220")
    private val PANEL = Color.parseColor("#111b30")
    private val GREEN = Color.parseColor("#16a34a")
    private val GRAY = Color.parseColor("#1e293b")
    private val MUTED = Color.parseColor("#94a3b8")
    private val BLUE = Color.parseColor("#60a5fa")
    private val AMBER = Color.parseColor("#fbbf24")

    private lateinit var addrLabel: TextView
    private lateinit var connNote: TextView
    private lateinit var setupView: LinearLayout
    private lateinit var mainView: LinearLayout
    private lateinit var addrInput: EditText
    private lateinit var setupMsg: TextView
    private lateinit var nowBg: GradientDrawable
    private lateinit var nowLab: TextView
    private lateinit var nowNum: TextView
    private lateinit var nowWho: TextView
    private lateinit var listBox: LinearLayout
    private lateinit var moreView: TextView
    private lateinit var countView: TextView
    private lateinit var qrView: ImageView
    private lateinit var qrText: TextView

    private val ticker = object : Runnable {
        override fun run() {
            poll()
            handler.postDelayed(this, 2500)
        }
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
    private fun px(v: Float) = v * scale

    private fun lp(w: Int, h: Int, weight: Float = 0f, top: Int = 0, left: Int = 0) =
        LinearLayout.LayoutParams(w, h, weight).apply { topMargin = dp(top); leftMargin = dp(left) }

    /** 기준 해상도(1280x720)의 px 값을 화면 크기에 맞춰 줄이고 늘려서 쓰는 텍스트 */
    private fun tv(text: String, ref: Float, color: Int, bold: Boolean = false, center: Boolean = false) =
        TextView(this).apply {
            this.text = text
            setTextSize(TypedValue.COMPLEX_UNIT_PX, px(ref))
            setTextColor(color)
            if (bold) setTypeface(typeface, Typeface.BOLD)
            if (center) gravity = Gravity.CENTER
        }

    private fun setPx(t: TextView, ref: Float) = t.setTextSize(TypedValue.COMPLEX_UNIT_PX, px(ref))

    private fun round(color: Int, r: Int = 18) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = dp(r).toFloat()
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

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        val b = base
        val onMain = b != null && mainView.visibility == View.VISIBLE
        setContentView(buildUi())
        if (onMain && b != null) {
            showMain(b)
            lastBoard?.let { showBoard(it) }
        } else {
            showSetup(null)
        }
    }

    // ---------------- 화면 구성 ----------------
    private fun buildUi(): View {
        val dm = resources.displayMetrics
        val w = dm.widthPixels
        val h = dm.heightPixels
        scale = minOf(w / 1280f, h / 720f).coerceIn(0.45f, 1.7f)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(BG)
        }

        // 상단 바
        val head = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(12), dp(4), dp(6), dp(4))
            setBackgroundColor(PANEL)
        }
        head.addView(tv("🏥 대기 현황", 34f, Color.WHITE, true))
        addrLabel = tv("", 24f, AMBER).apply { setTextIsSelectable(true) }
        head.addView(addrLabel, lp(0, WRAP_CONTENT, 1f, 0, 14))
        head.addView(Button(this).apply {
            text = "＋ 등록"
            setOnClickListener { registerDialog() }
        })
        head.addView(Button(this).apply {
            text = "서버 변경"
            setOnClickListener { showSetup(null) }
        })
        root.addView(head, lp(MATCH_PARENT, WRAP_CONTENT))
        connNote = tv("", 22f, Color.parseColor("#fca5a5"))
        root.addView(connNote, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 0, 12))

        // --- 연결 화면 ---
        setupView = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(16), dp(20), dp(16))
            visibility = View.GONE
        }
        setupView.addView(tv("PC 프로그램 화면에 표시된\n서버 주소(IP:포트)를 입력하거나 QR을 스캔하세요.", 28f, Color.WHITE))
        setupView.addView(Button(this).apply {
            text = "QR 스캔으로 연결"
            setOnClickListener { scan() }
        }, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 14))
        addrInput = input("예: 192.168.0.10:9000").apply {
            imeOptions = EditorInfo.IME_ACTION_GO
            setOnEditorActionListener { _, _, _ -> tryConnect(text.toString()); true }
        }
        setupView.addView(addrInput, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 10))
        setupView.addView(Button(this).apply {
            text = "연결"
            setOnClickListener { tryConnect(addrInput.text.toString()) }
        }, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 4))
        setupMsg = tv("", 24f, AMBER)
        setupView.addView(setupMsg, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 10))
        setupView.addView(tv("※ 폰과 PC가 같은 Wi-Fi(또는 PC의 핫스팟)에 연결돼 있어야 하고, 입력한 IP:포트가 PC 화면의 주소와 같아야 합니다.", 20f, MUTED),
            lp(MATCH_PARENT, WRAP_CONTENT, 0f, 8))
        root.addView(setupView, lp(MATCH_PARENT, 0, 1f))

        // --- 메인: 왼쪽 대기표 / 오른쪽 QR ---
        mainView = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(8), dp(8), dp(8), dp(8))
            visibility = View.GONE
        }
        val left = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }

        nowBg = round(GREEN, 20)
        val now = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            background = nowBg
            setPadding(dp(8), dp(6), dp(8), dp(6))
        }
        nowLab = tv("현재 호출", 26f, Color.WHITE, false, true)
        nowNum = tv("-", 150f, Color.WHITE, true, true).apply { maxLines = 1; includeFontPadding = false }
        nowWho = tv("", 40f, Color.WHITE, true, true).apply { maxLines = 1; ellipsize = TextUtils.TruncateAt.END }
        now.addView(nowLab, lp(MATCH_PARENT, WRAP_CONTENT))
        now.addView(nowNum, lp(MATCH_PARENT, WRAP_CONTENT))
        now.addView(nowWho, lp(MATCH_PARENT, WRAP_CONTENT))
        left.addView(now, lp(MATCH_PARENT, 0, 2f))

        val next = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = round(PANEL)
            setPadding(dp(12), dp(8), dp(12), dp(8))
        }
        next.addView(tv("다음 순서", 26f, MUTED))
        listBox = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        next.addView(listBox, lp(MATCH_PARENT, 0, 1f, 2))
        moreView = tv("", 24f, MUTED)
        next.addView(moreView, lp(MATCH_PARENT, WRAP_CONTENT))
        countView = tv("", 30f, Color.WHITE, true)
        next.addView(countView, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 2))
        left.addView(next, lp(MATCH_PARENT, 0, 3f, 8))
        mainView.addView(left, lp(0, MATCH_PARENT, 3f))

        // 오른쪽 QR
        val right = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            background = round(PANEL)
            setPadding(dp(8), dp(8), dp(8), dp(8))
        }
        right.addView(tv("📱 QR로 연결", 30f, Color.WHITE, true, true), lp(MATCH_PARENT, WRAP_CONTENT))
        val qrSide = minOf(w * 0.36f - dp(40), (h - dp(110)) * 0.62f).toInt().coerceAtLeast(dp(120))
        qrView = ImageView(this).apply {
            setBackgroundColor(Color.WHITE)
            scaleType = ImageView.ScaleType.FIT_CENTER
            setPadding(dp(6), dp(6), dp(6), dp(6))
        }
        right.addView(qrView, lp(qrSide, qrSide, 0f, 8))
        qrText = tv("", 24f, AMBER, false, true).apply { setTextIsSelectable(true) }
        right.addView(qrText, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 8))
        mainView.addView(right, lp(0, MATCH_PARENT, 2f, 0, 8))
        root.addView(mainView, lp(MATCH_PARENT, 0, 1f))

        // 화면 높이에 맞춰 보여 줄 대기 줄 수 계산
        val listH = (h - dp(110)) * 0.6f - px(120f)
        maxRows = (listH / px(56f)).toInt().coerceIn(1, 8)
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
        setupView.visibility = View.GONE
        mainView.visibility = View.VISIBLE
        addrLabel.text = "서버 $b"
        qrText.text = "daegi://$b"
        try {
            qrView.setImageBitmap(Qr.bitmap("daegi://$b", 900))
        } catch (e: Exception) {
            qrText.text = "QR 생성 오류: ${e.message}"
        }
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
                runOnUiThread {
                    connNote.text = ""
                    showBoard(board)
                }
            } catch (e: Exception) {
                runOnUiThread {
                    connNote.text = "⚠ 서버와 연결이 끊겼습니다 (${e.javaClass.simpleName}) — PC와 같은 네트워크인지 확인하세요"
                }
            }
        }
    }

    private fun showBoard(board: JSONObject) {
        lastBoard = board
        val cur = board.optJSONObject("current")
        if (cur == null) {
            nowBg.setColor(GRAY)
            nowLab.text = ""
            nowNum.text = "대기 없음"
            setPx(nowNum, 64f)
            nowWho.text = ""
        } else {
            nowBg.setColor(GREEN)
            nowLab.text = "현재 호출"
            nowNum.text = "${cur.optInt("id")}번"
            setPx(nowNum, 150f)
            nowWho.text = "${cur.optString("name")} 님 · ${cur.optInt("size")}명"
        }
        listBox.removeAllViews()
        val next = board.optJSONArray("next")
        val n = next?.length() ?: 0
        val show = minOf(n, maxRows)
        for (i in 0 until show) {
            val o = next!!.getJSONObject(i)
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
            }
            row.addView(tv("${o.optInt("id")}번", 34f, BLUE, true).apply { maxLines = 1 }, lp(px(110f).toInt(), WRAP_CONTENT))
            row.addView(tv(o.optString("name"), 32f, Color.WHITE).apply {
                maxLines = 1
                ellipsize = TextUtils.TruncateAt.END
            }, lp(0, WRAP_CONTENT, 1f))
            row.addView(tv("${o.optInt("size")}명", 28f, MUTED).apply { maxLines = 1 })
            listBox.addView(row, lp(MATCH_PARENT, 0, 1f))
        }
        val total = board.optInt("count", 0)
        val rest = total - 1 - show
        moreView.text = when {
            total <= 1 -> "다음 대기가 없습니다"
            rest > 0 -> "외 ${rest}팀 대기 중"
            else -> ""
        }
        countView.text = "대기 ${total}팀 · ${board.optInt("people", 0)}명"
    }

    // ---------------- 대기 등록 (상단 버튼) ----------------
    private fun registerDialog() {
        val b = base ?: run { showSetup("먼저 서버에 연결해 주세요."); return }
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(8), dp(20), 0)
        }
        val name = EditText(this).apply { hint = "이름"; setSingleLine() }
        val size = EditText(this).apply {
            hint = "인원"
            inputType = InputType.TYPE_CLASS_NUMBER
            setText("1")
        }
        box.addView(name)
        box.addView(size)
        AlertDialog.Builder(this)
            .setTitle("대기 등록")
            .setView(box)
            .setPositiveButton("대기표 받기") { _, _ ->
                val nm = name.text.toString()
                val sz = size.text.toString().trim().toIntOrNull() ?: 0
                io.execute {
                    try {
                        val r = call(b, JSONObject().put("cmd", "join").put("name", nm).put("size", sz))
                        runOnUiThread {
                            val msg = if (r.optBoolean("ok")) "대기번호 ${r.optInt("id")}번이 발급되었습니다."
                            else r.optString("error", "등록하지 못했습니다")
                            AlertDialog.Builder(this).setMessage(msg).setPositiveButton("확인", null).show()
                            poll()
                        }
                    } catch (e: Exception) {
                        runOnUiThread {
                            AlertDialog.Builder(this).setMessage("서버에 연결하지 못했습니다 (${e.javaClass.simpleName})")
                                .setPositiveButton("확인", null).show()
                        }
                    }
                }
            }
            .setNegativeButton("취소", null)
            .show()
    }

    override fun onDestroy() {
        handler.removeCallbacks(ticker)
        io.shutdownNow()
        super.onDestroy()
    }
}
