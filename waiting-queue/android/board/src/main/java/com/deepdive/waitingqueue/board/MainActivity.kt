package com.deepdive.waitingqueue.board

import android.app.Activity
import android.app.AlertDialog
import android.content.res.Configuration
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.Gravity
import android.view.KeyEvent
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.view.WindowManager
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.io.File

/**
 * 대기표 + QR 앱 (한 화면): 이 기기가 서버가 되고, 대기 현황과 등록 QR을 앱 화면에 직접 그린다.
 * 손님은 폰 카메라로 QR을 찍으면 등록 페이지가 열린다. 웹뷰를 쓰지 않는다.
 */
class MainActivity : Activity() {
    private lateinit var queue: WaitingQueue
    private var server: QueueServer? = null
    private var port = 0
    private val handler = Handler(Looper.getMainLooper())
    private var lastUrl = ""
    private var errorText: String? = null

    private lateinit var hintView: TextView
    private lateinit var nowBg: GradientDrawable
    private lateinit var nowLab: TextView
    private lateinit var nowNum: TextView
    private lateinit var nowWho: TextView
    private lateinit var listBox: LinearLayout
    private lateinit var moreView: TextView
    private lateinit var qrView: ImageView
    private lateinit var urlView: TextView
    private lateinit var countView: TextView

    private val BG = Color.parseColor("#0b1220")
    private val PANEL = Color.parseColor("#111b30")
    private val GREEN = Color.parseColor("#16a34a")
    private val GRAY = Color.parseColor("#1e293b")
    private val MUTED = Color.parseColor("#94a3b8")
    private val BLUE = Color.parseColor("#60a5fa")

    private val ticker = object : Runnable {
        override fun run() {
            try { refresh() } catch (e: Exception) { errorText = "화면 갱신 오류: ${e.message}" }
            handler.postDelayed(this, 1500)
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
            if (bold) setTypeface(typeface, android.graphics.Typeface.BOLD)
            if (center) gravity = Gravity.CENTER
        }

    private fun round(color: Int, r: Int = 20) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = dp(r).toFloat()
    }

    private fun mask(n: String): String {
        val a = n.codePoints().toArray()
        fun s(i: Int, j: Int) = String(a, i, j - i)
        return when {
            a.size <= 1 -> n
            a.size == 2 -> s(0, 1) + "*"
            else -> s(0, 1) + "*".repeat(a.size - 2) + s(a.size - 1, a.size)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        queue = WaitingQueue(File(filesDir, "data.json"))
        val cache = HashMap<String, String>()
        val srv = QueueServer(
            queue = queue,
            loadAsset = { name ->
                cache.getOrPut(name) { assets.open(name).bufferedReader(Charsets.UTF_8).use { it.readText() } }
            },
            joinUrl = { p -> "http://${NetUtil.lanIp() ?: "127.0.0.1"}:$p/join" },
            hint = { "" },
        )
        server = srv
        try {
            port = srv.start(8080)
        } catch (e: Exception) {
            errorText = "서버 시작 오류: ${e.message}"
        }
        setContentView(buildUi())
        handler.post(ticker)
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        lastUrl = ""
        setContentView(buildUi())
        refresh()
    }

    private fun buildUi(): View {
        val land = resources.displayMetrics.widthPixels > resources.displayMetrics.heightPixels
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(BG)
        }

        // 헤더
        val head = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(16), dp(10), dp(16), dp(10))
            setBackgroundColor(PANEL)
        }
        head.addView(tv("🏥 대기 현황", 22f, Color.WHITE, true), lp(0, WRAP_CONTENT, 1f))
        hintView = tv("", 13f, MUTED).apply { setTextIsSelectable(true) }
        head.addView(hintView, lp(WRAP_CONTENT, WRAP_CONTENT))
        root.addView(head, lp(MATCH_PARENT, WRAP_CONTENT))

        // 본문
        val main = LinearLayout(this).apply {
            orientation = if (land) LinearLayout.HORIZONTAL else LinearLayout.VERTICAL
            setPadding(dp(12), dp(12), dp(12), dp(12))
        }
        val left = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }

        // 현재 호출 카드
        nowBg = round(GREEN, 24)
        val now = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = nowBg
            setPadding(dp(16), dp(16), dp(16), dp(16))
        }
        nowLab = tv("현재 호출", 18f, Color.WHITE, false, true)
        nowNum = tv("-", 84f, Color.WHITE, true, true)
        nowWho = tv("", 26f, Color.WHITE, true, true)
        now.addView(nowLab, lp(MATCH_PARENT, WRAP_CONTENT))
        now.addView(nowNum, lp(MATCH_PARENT, WRAP_CONTENT))
        now.addView(nowWho, lp(MATCH_PARENT, WRAP_CONTENT))
        left.addView(now, lp(MATCH_PARENT, WRAP_CONTENT))

        // 다음 순서
        val next = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = round(PANEL)
            setPadding(dp(16), dp(12), dp(16), dp(12))
        }
        next.addView(tv("다음 순서 (눌러서 삭제)", 16f, MUTED))
        listBox = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        next.addView(listBox, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 6))
        moreView = tv("", 15f, MUTED)
        next.addView(moreView, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 6))
        left.addView(next, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 12))

        // QR 카드
        val right = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            background = round(PANEL)
            setPadding(dp(16), dp(16), dp(16), dp(16))
        }
        right.addView(tv("📱 QR을 찍어 대기 등록", 20f, Color.WHITE, true, true), lp(MATCH_PARENT, WRAP_CONTENT))
        qrView = ImageView(this).apply {
            setBackgroundColor(Color.WHITE)
            adjustViewBounds = true
            scaleType = ImageView.ScaleType.FIT_CENTER
            maxHeight = (resources.displayMetrics.heightPixels * 0.55).toInt()
            setPadding(dp(8), dp(8), dp(8), dp(8))
        }
        right.addView(qrView, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 12))
        urlView = tv("", 15f, Color.WHITE, false, true).apply { setTextIsSelectable(true) }
        right.addView(urlView, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 10))
        countView = tv("", 20f, MUTED, false, true)
        right.addView(countView, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 6))

        if (land) {
            main.addView(left, lp(0, WRAP_CONTENT, 1.5f))
            main.addView(right, lp(0, WRAP_CONTENT, 1f, 0, 12))
        } else {
            main.addView(left, lp(MATCH_PARENT, WRAP_CONTENT))
            main.addView(right, lp(MATCH_PARENT, WRAP_CONTENT, 0f, 12))
        }
        root.addView(ScrollView(this).apply { addView(main) }, lp(MATCH_PARENT, 0, 1f))

        // 하단 버튼
        val btns = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(12), dp(8), dp(12), dp(12))
            setBackgroundColor(PANEL)
        }
        btns.addView(Button(this).apply {
            text = "▶ 다음 손님 호출 (K)"
            textSize = 18f
            setOnClickListener { complete() }
        }, lp(0, dp(64), 2f))
        btns.addView(Button(this).apply {
            text = "＋ 추가"
            textSize = 16f
            setOnClickListener { addDialog() }
        }, lp(0, dp(64), 1f, 0, 8))
        root.addView(btns, lp(MATCH_PARENT, WRAP_CONTENT))
        return root
    }

    private fun refresh() {
        val snap = queue.snapshot()
        val items = snap.getJSONArray("items")
        val n = items.length()

        if (n == 0) {
            nowBg.setColor(GRAY)
            nowLab.text = ""
            nowNum.text = "대기 없음"
            nowNum.textSize = 40f
            nowWho.text = ""
        } else {
            val top = items.getJSONObject(0)
            nowBg.setColor(GREEN)
            nowLab.text = "현재 호출"
            nowNum.text = "${top.getInt("id")}번"
            nowNum.textSize = 84f
            nowWho.text = "${mask(top.getString("name"))} 님 · ${top.getInt("size")}명"
        }

        listBox.removeAllViews()
        val show = minOf(n - 1, 5)
        for (i in 1..show) {
            val o = items.getJSONObject(i)
            val id = o.getInt("id")
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                setPadding(0, dp(8), 0, dp(8))
                setOnClickListener { confirmRemove(id, mask(o.getString("name"))) }
            }
            row.addView(tv("${id}번", 24f, BLUE, true), lp(dp(84), WRAP_CONTENT))
            row.addView(tv(mask(o.getString("name")), 22f, Color.WHITE), lp(0, WRAP_CONTENT, 1f))
            row.addView(tv("${o.getInt("size")}명", 20f, MUTED), lp(WRAP_CONTENT, WRAP_CONTENT))
            listBox.addView(row, lp(MATCH_PARENT, WRAP_CONTENT))
        }
        moreView.text = when {
            n <= 1 -> "다음 대기가 없습니다"
            n - 1 > show -> "외 ${n - 1 - show}팀 대기 중"
            else -> ""
        }
        countView.text = "대기 ${n}팀 · ${snap.getInt("totalPeople")}명"

        val ip = NetUtil.lanIp()
        hintView.text = errorText ?: when {
            port == 0 -> "❌ 서버 시작 실패"
            ip == null -> "⚠ Wi-Fi/핫스팟을 켜 주세요"
            else -> "서버 $ip:$port"
        }
        val url = "http://${ip ?: "127.0.0.1"}:$port/join"
        if (url != lastUrl) {
            lastUrl = url
            try {
                qrView.setImageBitmap(Qr.bitmap(url))
            } catch (e: Exception) {
                errorText = "QR 생성 오류: ${e.message}"
            }
            urlView.text = url
        }
    }

    private fun complete() {
        queue.complete()
        refresh()
    }

    private fun confirmRemove(id: Int, name: String) {
        AlertDialog.Builder(this)
            .setTitle("대기 삭제")
            .setMessage("${id}번 $name 님을 삭제할까요?")
            .setPositiveButton("삭제") { _, _ -> queue.remove(id, null, true); refresh() }
            .setNegativeButton("취소", null)
            .show()
    }

    private fun addDialog() {
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
            .setTitle("대기 추가")
            .setView(box)
            .setPositiveButton("추가") { _, _ ->
                try {
                    queue.add(name.text.toString(), size.text.toString())
                    refresh()
                } catch (e: IllegalArgumentException) {
                    Toast.makeText(this, e.message ?: "입력을 확인해 주세요", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton("취소", null)
            .show()
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent): Boolean {
        if (keyCode == KeyEvent.KEYCODE_K) {
            complete()
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    override fun onDestroy() {
        handler.removeCallbacks(ticker)
        server?.stop()
        super.onDestroy()
    }
}
