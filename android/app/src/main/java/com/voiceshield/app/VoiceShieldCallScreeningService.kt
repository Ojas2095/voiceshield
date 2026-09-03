package com.voiceshield.app

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.telecom.Call
import android.telecom.CallScreeningService
import android.util.Log

/**
 * VoiceShield Call Screening Service
 * ===================================
 * Intercepts incoming calls at the OS level before they ring the phone.
 * Analyzes initial Layer 3 signals (international route, prefix, spam frequency)
 * and spawns the VoiceShield floating in-call HUD overlay when answered.
 */
class VoiceShieldCallScreeningService : CallScreeningService() {

    override fun onScreenCall(callDetails: Call.Details) {
        val handle: Uri? = callDetails.handle
        val phoneNumber = handle?.schemeSpecificPart ?: "UNKNOWN"
        Log.i(TAG, "Incoming call screened: $phoneNumber")

        // Layer 3 Metadata Signal Analysis
        val isBlocked = checkBlacklistedPrefix(phoneNumber)
        
        val response = CallResponse.Builder()
            .setDisallowCall(isBlocked)
            .setRejectCall(isBlocked)
            .setSkipCallLog(false)
            .setSkipNotification(isBlocked)
            .build()

        respondToCall(callDetails, response)

        if (!isBlocked) {
            // Launch floating In-Call HUD overlay
            val overlayIntent = Intent(this, VoiceShieldOverlayService::class.java).apply {
                putExtra("PHONE_NUMBER", phoneNumber)
                putExtra("CALL_TYPE", if (callDetails.callDirection == Call.Details.DIRECTION_INCOMING) "INCOMING" else "OUTGOING")
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(overlayIntent)
            } else {
                startService(overlayIntent)
            }
        }
    }

    private fun checkBlacklistedPrefix(number: String): Boolean {
        // High-risk VoIP prefixes commonly associated with digital arrest extortion
        val highRiskPrefixes = listOf("+92", "+234", "+880", "+7")
        return highRiskPrefixes.any { number.startsWith(it) }
    }

    companion object {
        private const val TAG = "VoiceShieldScreening"
    }
}
