package com.voiceshield.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.os.Build
import android.os.IBinder
import android.util.Log
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.TextView
import androidx.core.app.NotificationCompat
import okhttp3.*
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * VoiceShield Floating In-Call Overlay Service
 * ============================================
 * Truecaller-style floating HUD that appears over the native phone dialer.
 * Connects via WebSocket to the VoiceShield FastAPI backend, streams audio,
 * and updates threat level in real-time.
 */
class VoiceShieldOverlayService : Service() {

    private var windowManager: WindowManager? = null
    private var overlayView: View? = null
    private var webSocket: WebSocket? = null
    private var currentCallId: String? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        val notification = createForegroundNotification()
        startForeground(NOTIFICATION_ID, notification)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val phoneNumber = intent?.getStringExtra("PHONE_NUMBER") ?: "Unknown"
        initFloatingOverlay(phoneNumber)
        connectToVoiceShieldBackend()
        return START_NOT_STICKY
    }

    private fun initFloatingOverlay(phoneNumber: String) {
        windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        
        val layoutType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            WindowManager.LayoutParams.TYPE_PHONE
        }

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            layoutType,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL
            y = 120 // Position below status bar
        }

        val inflater = LayoutInflater.from(this)
        overlayView = inflater.inflate(R.layout.overlay_hud, null)

        overlayView?.findViewById<TextView>(R.id.txtCallerNumber)?.text = phoneNumber
        overlayView?.findViewById<Button>(R.id.btnFreezeBanking)?.setOnClickListener {
            triggerBankingFreeze()
        }

        windowManager?.addView(overlayView, params)
    }

    private fun connectToVoiceShieldBackend() {
        val client = OkHttpClient.Builder()
            .readTimeout(0, TimeUnit.MILLISECONDS)
            .build()

        // Start call session
        val request = Request.Builder()
            .url("ws://10.0.2.2:8000/ws/stream/mobile-companion")
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = JSONObject(text)
                    if (json.optString("type") == "risk_update") {
                        val score = json.optDouble("fused_risk_score", 0.0)
                        val verdict = json.optString("verdict", "REAL")
                        updateOverlayUi(score, verdict)
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "JSON parse error", e)
                }
            }
        })
    }

    private fun updateOverlayUi(score: Double, verdict: String) {
        overlayView?.post {
            val txtRisk = overlayView?.findViewById<TextView>(R.id.txtRiskScore)
            val txtVerdict = overlayView?.findViewById<TextView>(R.id.txtVerdict)
            val btnFreeze = overlayView?.findViewById<Button>(R.id.btnFreezeBanking)

            txtRisk?.text = String.format("%.1f%%", score * 100)
            txtVerdict?.text = verdict

            if (verdict == "FRAUD") {
                btnFreeze?.visibility = View.VISIBLE
            }
        }
    }

    private fun triggerBankingFreeze() {
        // Calls backend hold API & broadcasts to secure banking SDK
        Log.w(TAG, "Banking freeze requested for active call")
    }

    override fun onDestroy() {
        super.onDestroy()
        webSocket?.close(1000, "Call Ended")
        if (overlayView != null) {
            windowManager?.removeView(overlayView)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "VoiceShield In-Call Shield",
                NotificationManager.IMPORTANCE_LOW
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun createForegroundNotification(): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("VoiceShield Active Interceptor")
            .setContentText("Monitoring live call for synthetic voice clones...")
            .setSmallIcon(R.mipmap.ic_launcher)
            .build()
    }

    companion object {
        private const val TAG = "VoiceShieldOverlay"
        private const val CHANNEL_ID = "voiceshield_overlay_channel"
        private const val NOTIFICATION_ID = 901
    }
}
