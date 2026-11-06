package com.deepdive.waitingqueue.board

import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.URLDecoder
import java.util.concurrent.Executors

class Req(val method: String, val path: String, val query: Map<String, String>,
          val headers: Map<String, String>, val body: ByteArray)

class Res(val code: Int, val body: ByteArray, val type: String)

/** 소켓으로 직접 구현한 작은 HTTP 서버 (Python 버전과 같은 동작). */
class QueueServer(
    private val queue: WaitingQueue,
    private val loadAsset: (String) -> String,
    private val joinUrl: (Int) -> String,
    private val hint: () -> String,
) {
    var port: Int = 0
        private set
    private var server: ServerSocket? = null
    private val pool = Executors.newCachedThreadPool()
    @Volatile private var running = false

    private val json = "application/json; charset=utf-8"
    private val html = "text/html; charset=utf-8"

    fun start(preferred: Int): Int {
        var p = preferred
        while (p < preferred + 20 && server == null) {
            try {
                val s = ServerSocket()
                s.reuseAddress = true
                s.bind(InetSocketAddress(p))
                server = s
                port = p
            } catch (e: Exception) {
                p++
            }
        }
        val s = server ?: throw IllegalStateException("사용할 수 있는 포트가 없습니다")
        running = true
        Thread {
            while (running) {
                try {
                    val c = s.accept()
                    pool.execute { serve(c) }
                } catch (e: Exception) {
                    if (!running) break
                }
            }
        }.apply { isDaemon = true; start() }
        return port
    }

    fun stop() {
        running = false
        try { server?.close() } catch (e: Exception) { }
        pool.shutdownNow()
    }

    private fun serve(sock: Socket) {
        try {
            sock.soTimeout = 10000
            val req = readRequest(sock) ?: return
            val local = sock.inetAddress.isLoopbackAddress &&
                listOf("cf-connecting-ip", "x-forwarded-for", "forwarded", "x-real-ip").none { req.headers.containsKey(it) }
            val res = try {
                route(req, local)
            } catch (e: Exception) {
                Res(500, """{"error":"서버 오류"}""".toByteArray(), json)
            }
            val status = mapOf(200 to "OK", 204 to "No Content", 400 to "Bad Request",
                403 to "Forbidden", 404 to "Not Found", 500 to "Internal Server Error")[res.code] ?: "OK"
            val head = "HTTP/1.1 ${res.code} $status\r\nContent-Type: ${res.type}\r\n" +
                "Content-Length: ${res.body.size}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n"
            val out = sock.getOutputStream()
            out.write(head.toByteArray(Charsets.ISO_8859_1))
            out.write(res.body)
            out.flush()
        } catch (e: Exception) {
            // 연결 오류는 무시
        } finally {
            try { sock.close() } catch (e: Exception) { }
        }
    }

    private fun headerEnd(b: ByteArray): Int {
        for (i in 0..b.size - 4) {
            if (b[i] == 13.toByte() && b[i + 1] == 10.toByte() && b[i + 2] == 13.toByte() && b[i + 3] == 10.toByte()) return i
        }
        return -1
    }

    private fun readRequest(sock: Socket): Req? {
        val ins = sock.getInputStream()
        val buf = ByteArrayOutputStream()
        val tmp = ByteArray(4096)
        var end = -1
        var all = ByteArray(0)
        while (end < 0) {
            val n = ins.read(tmp)
            if (n < 0) return null
            buf.write(tmp, 0, n)
            if (buf.size() > 32768) return null
            all = buf.toByteArray()
            end = headerEnd(all)
        }
        val lines = String(all, 0, end, Charsets.ISO_8859_1).split("\r\n")
        val first = lines[0].split(" ")
        if (first.size < 2) return null
        val headers = HashMap<String, String>()
        for (i in 1 until lines.size) {
            val c = lines[i].indexOf(':')
            if (c > 0) headers[lines[i].substring(0, c).trim().lowercase()] = lines[i].substring(c + 1).trim()
        }
        val len = minOf(headers["content-length"]?.toIntOrNull() ?: 0, 10000)
        val body = ByteArrayOutputStream()
        val have = all.size - (end + 4)
        if (have > 0) body.write(all, end + 4, minOf(have, len))
        while (body.size() < len) {
            val n = ins.read(tmp)
            if (n < 0) break
            body.write(tmp, 0, minOf(n, len - body.size()))
        }
        val target = first[1]
        val q = target.indexOf('?')
        val path = if (q >= 0) target.substring(0, q) else target
        val query = HashMap<String, String>()
        if (q >= 0) {
            for (kv in target.substring(q + 1).split("&")) {
                val e = kv.indexOf('=')
                if (e > 0) query[URLDecoder.decode(kv.substring(0, e), "UTF-8")] = URLDecoder.decode(kv.substring(e + 1), "UTF-8")
            }
        }
        return Req(first[0].uppercase(), path, query, headers, body.toByteArray())
    }

    private fun j(code: Int, o: JSONObject) = Res(code, o.toString().toByteArray(Charsets.UTF_8), json)
    private fun page(s: String) = Res(200, s.toByteArray(Charsets.UTF_8), html)

    private fun parseBody(b: ByteArray): JSONObject =
        try { JSONObject(String(b, Charsets.UTF_8)) } catch (e: Exception) { JSONObject() }

    private fun route(req: Req, local: Boolean): Res {
        val p = req.path
        if (p in setOf("/", "/admin", "/board", "/api/queue", "/api/info", "/api/complete") && !local) {
            return j(403, JSONObject().put("error", "관리 기능은 서버 폰에서만 사용할 수 있습니다"))
        }
        if (req.method == "GET") {
            when (p) {
                "/", "/admin" -> return page(loadAsset("admin.html").replace("BUILD_ID", "apk-v1"))
                "/board" -> return page(loadAsset("board.html"))
                "/join" -> return page(loadAsset("join.html"))
                "/api/queue" -> return j(200, queue.snapshot())
                "/api/status" -> return j(200, queue.status(req.query["id"]?.toIntOrNull() ?: 0))
                "/api/info" -> {
                    val url = joinUrl(port)
                    return j(200, JSONObject().put("joinUrl", url).put("svg", Qr.svg(url))
                        .put("tunnel", false).put("pending", false).put("hint", hint()))
                }
                "/favicon.ico" -> return Res(204, ByteArray(0), "text/plain")
            }
        } else if (req.method == "POST") {
            val b = parseBody(req.body)
            when (p) {
                "/api/join" -> return try {
                    val it = queue.add(b.optString("name", ""), b.opt("size"))
                    j(200, it.toJson(true))
                } catch (e: IllegalArgumentException) {
                    j(400, JSONObject().put("error", e.message ?: "잘못된 요청"))
                }
                "/api/complete" -> {
                    val done = queue.complete()
                    return j(200, JSONObject().put("done", done?.toJson() ?: JSONObject.NULL))
                }
                "/api/remove" -> {
                    val id = b.optInt("id", 0)
                    val tok = if (b.has("token") && !b.isNull("token")) b.getString("token") else null
                    return j(200, JSONObject().put("ok", queue.remove(id, tok, local)))
                }
            }
        }
        return Res(404, "Not found".toByteArray(), "text/plain")
    }
}
