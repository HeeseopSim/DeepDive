package com.deepdive.waitingqueue

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.SecureRandom

/** 대기열 로직. 맨 앞(0번)이 현재 차례. */
data class Item(val id: Int, val name: String, val size: Int, val createdAt: Long, val token: String) {
    fun toJson(withToken: Boolean = false): JSONObject = JSONObject()
        .put("id", id).put("name", name).put("size", size).put("createdAt", createdAt)
        .also { if (withToken) it.put("token", token) }
}

class WaitingQueue(private val file: File?) {
    private val items = mutableListOf<Item>()
    private var nextNumber = 1
    private var lastCalled: Int? = null

    init { load() }

    private fun load() {
        try {
            if (file == null || !file.exists()) return
            val d = JSONObject(file.readText())
            val arr = d.optJSONArray("items") ?: JSONArray()
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i)
                items.add(Item(o.getInt("id"), o.getString("name"), o.getInt("size"),
                    o.optLong("createdAt"), o.optString("token")))
            }
            nextNumber = d.optInt("nextNumber", 1)
            if (d.has("lastCalled") && !d.isNull("lastCalled")) lastCalled = d.getInt("lastCalled")
        } catch (e: Exception) {
            items.clear()  // 손상된 파일은 무시
        }
    }

    private fun save() {
        try {
            if (file == null) return
            val arr = JSONArray()
            items.forEach { arr.put(it.toJson(true)) }
            file.writeText(JSONObject().put("items", arr).put("nextNumber", nextNumber)
                .put("lastCalled", lastCalled ?: JSONObject.NULL).toString())
        } catch (e: Exception) { /* 저장 실패는 무시 (메모리 상태는 유지) */ }
    }

    private fun newToken(): String {
        val b = ByteArray(8); SecureRandom().nextBytes(b)
        return b.joinToString("") { "%02x".format(it) }
    }

    @Synchronized
    fun add(nameIn: String?, sizeIn: Any?): Item {
        val name = (nameIn ?: "").trim().take(30)
        val size = when (sizeIn) {
            is Number -> sizeIn.toInt()
            is String -> sizeIn.trim().toIntOrNull() ?: 0
            else -> 0
        }
        if (name.isEmpty()) throw IllegalArgumentException("이름을 입력해주세요")
        if (size !in 1..99) throw IllegalArgumentException("인원은 1~99명이어야 합니다")
        val item = Item(nextNumber++, name, size, System.currentTimeMillis(), newToken())
        items.add(item); save()
        return item
    }

    /** K키: 맨 위 사람 삭제 → 다음 사람이 맨 위로. */
    @Synchronized
    fun complete(): Item? {
        val done = if (items.isEmpty()) null else items.removeAt(0)
        if (done != null) lastCalled = done.id
        save()
        return done
    }

    @Synchronized
    fun remove(id: Int, token: String?, admin: Boolean): Boolean {
        val i = items.indexOfFirst { it.id == id }
        if (i < 0) return false
        if (!admin && (token.isNullOrEmpty() || token != items[i].token)) return false
        items.removeAt(i); save()
        return true
    }

    @Synchronized
    fun status(id: Int): JSONObject {
        val i = items.indexOfFirst { it.id == id }
        val last = lastCalled ?: JSONObject.NULL
        if (i < 0) return JSONObject().put("waiting", false).put("lastCalled", last)
        return JSONObject().put("waiting", true).put("position", i + 1).put("teamsAhead", i)
            .put("peopleAhead", items.take(i).sumOf { it.size })
            .put("item", items[i].toJson()).put("lastCalled", last)
    }

    @Synchronized
    fun snapshot(): JSONObject {
        val arr = JSONArray()
        items.forEach { arr.put(it.toJson()) }
        return JSONObject().put("items", arr).put("totalPeople", items.sumOf { it.size })
            .put("lastCalled", lastCalled ?: JSONObject.NULL)
    }
}
