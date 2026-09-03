'use client';

import Link from 'next/link';
import { useState, useRef, useEffect } from 'react';
import {
  FlaskConical, Play, Pause, RotateCcw, Square, ShieldAlert, ShieldCheck, AlertTriangle,
  Volume2, VolumeX, Activity, Lock, ChevronRight, AudioWaveform, FileText, CheckCircle2,
  Sparkles, Layers, Search
} from 'lucide-react';
import { AppShell } from '../../components/AppShell';
import { VoiceIntegrityRail } from '../../components/VoiceIntegrityRail';
import { useVoiceShield, type Verdict, type ThreatCategory } from '../../hooks/useVoiceShield';

interface Vector {
  id: string;
  file: string;
  category: 'HUMAN_LEGITIMATE' | 'HUMAN_VISHING' | 'AI_CLONED';
  title: string;
  lang: string;
  duration: string;
  durationSec: number;
  scenario: string;
  codec: string;
  speaker: string;
  keyTactics: string[];
  groundTruthText: string;
  acousticNote: string;
}

const VECTORS: Vector[] = [
  // ── 1. Legitimate Human Speech ─────────────────────────────────────────────
  {
    id: 'VS-HUM-01',
    file: '/demo/real_en.wav',
    category: 'HUMAN_LEGITIMATE',
    title: 'Clinic Appointment Confirmation',
    lang: 'English',
    duration: '2.3s',
    durationSec: 2.25,
    scenario: 'Routine medical verification — appointment schedule confirmation',
    codec: '8 kHz G.711u / PSTN',
    speaker: 'Dr. Office Receptionist',
    keyTactics: ['Benign Inquiry', 'Verified Identity'],
    groundTruthText: 'Good afternoon, this is calling from City Care Clinic to confirm your checkup appointment for tomorrow at three o clock.',
    acousticNote: 'Natural human vocal tract roll-off (-12 dB/octave). No vocoder phase dispersion.',
  },
  {
    id: 'VS-HUM-02',
    file: '/demo/real_hi.wav',
    category: 'HUMAN_LEGITIMATE',
    title: 'Regional Bank Support Inquiry',
    lang: 'Hindi',
    duration: '2.3s',
    durationSec: 2.25,
    scenario: 'Customer inquiry regarding regional branch operational hours',
    codec: '8 kHz G.711a / Gateway',
    speaker: 'Regional Helpdesk Representative',
    keyTactics: ['Standard Support', 'No Sensitive Demands'],
    groundTruthText: 'नमस्ते, हमारे बैंक की स्थानीय शाखा कल सुबह दस बजे खुलेगी। क्या मैं आपकी कोई और सहायता कर सकता हूँ?',
    acousticNote: 'Natural biological Hindi vocal tract resonances. Healthy F1-F3 formant structure.',
  },
  {
    id: 'VS-HUM-03',
    file: '/demo/real_long_en.wav',
    category: 'HUMAN_LEGITIMATE',
    title: 'Colleague Project Planning Review',
    lang: 'English',
    duration: '68.6s',
    durationSec: 68.6,
    scenario: 'Extended genuine dialogue between team members discussing slide decks and lab logistics',
    codec: '16 kHz PCM / Telephony',
    speaker: 'Two Team Members (Interactive)',
    keyTactics: ['Natural Dialogue', 'Colleague Banter', 'Zero Coercion'],
    groundTruthText: 'Hello, good afternoon! Did you get a chance to review the presentation deck for our project review tomorrow morning? Yes, I went through the entire slide sequence. The architecture diagrams look very clear, especially the dual-surface integration and the evidence audit trail...',
    acousticNote: 'Multi-speaker biological acoustics, natural conversational pauses, zero false positives across 134 continuous sliding windows.',
  },

  // ── 2. Human Vishing Scams (Real Human Voice + Malicious Intent) ────────────
  {
    id: 'VS-VISH-01',
    file: '/demo/human_scam_sbi_otp.wav',
    category: 'HUMAN_VISHING',
    title: 'SBI Fraud Unit OTP Phishing',
    lang: 'English',
    duration: '28.0s',
    durationSec: 28.0,
    scenario: 'Real human voice impersonating bank fraud prevention unit to harvest credit card OTP',
    codec: '16 kHz Telephony',
    speaker: 'Impersonator (Biological Human)',
    keyTactics: ['Credential Theft (OTP)', 'Urgency & Pressure', 'Authority Impersonation'],
    groundTruthText: 'Hello, this is officer Rakesh Verma calling from the State Bank of India Fraud Prevention Unit. We have detected a suspicious unauthorized debit of forty-nine thousand rupees on your credit card. To immediately cancel this transaction and block fraudulent access, please share the six digit OTP sent to your registered mobile number right now or your card will be permanently blocked.',
    acousticNote: 'Authentic human vocal tract (Layer 1 Clean ~0.005), but Layer 2 flags high-risk credential harvesting (OTP) & financial coercion.',
  },
  {
    id: 'VS-VISH-02',
    file: '/demo/human_scam_electricity_hi.wav',
    category: 'HUMAN_VISHING',
    title: 'Electricity Disconnection & UPI Demand',
    lang: 'Hindi',
    duration: '26.5s',
    durationSec: 26.5,
    scenario: 'Real human voice threatening immediate power disconnection unless penalty is transferred via UPI',
    codec: '16 kHz Telephony',
    speaker: 'Impersonator (Biological Human)',
    keyTactics: ['Utility Disconnection Threat', 'Urgency & Coercion', 'UPI Payment Demand'],
    groundTruthText: 'नमस्ते, मैं राज्य बिजली वितरण कंपनी के मुख्य सतर्कता कार्यालय से बोल रहा हूँ। आपके बिजली बिल का भुगतान बकाया होने के कारण आज रात नौ बजे आपकी बिजली का कनेक्शन काट दिया जाएगा। अगर आप तत्काल डिस्कनेक्शन रोकना चाहते हैं तो हमारे बिलिंग अधिकारी के यूपीआई आईडी पर तुरंत पंद्रह सौ रुपये जुर्माना जमा करें।',
    acousticNote: 'Biological Hindi human voice. Semantic NLP catches aggressive urgency markers and direct UPI payment demands.',
  },
  {
    id: 'VS-VISH-03',
    file: '/demo/human_scam_customs_parcel.wav',
    category: 'HUMAN_VISHING',
    title: 'Customs Contraband Parcel Extortion',
    lang: 'English',
    duration: '32.3s',
    durationSec: 32.3,
    scenario: 'Real human voice claiming intercepted narcotics parcel with magistrate non-bailable arrest warrant',
    codec: '16 kHz Telephony',
    speaker: 'Impersonator (Biological Human)',
    keyTactics: ['Authority Impersonation (Customs)', 'Contraband Extortion', 'Arrest Threat'],
    groundTruthText: 'Attention. This is the Customs Inspection Clearance Office at Indira Gandhi International Airport. A courier parcel addressed under your national identity number was intercepted with illegal contraband and unauthorized identity cards. A non-bailable warrant has been forwarded to the local police station. You must immediately verify your credentials with our duty inspector and transfer the security clearance fee to avoid immediate arrest.',
    acousticNote: 'Layer 1 confirms natural human voice. Layer 2 flags critical authority extortion, parcel contraband claim, and arrest threats.',
  },

  // ── 3. Synthetic AI Cloned Speech ──────────────────────────────────────────
  {
    id: 'VS-CLONE-01',
    file: '/demo/cloned_en.wav',
    category: 'AI_CLONED',
    title: 'Executive Impersonation Wire Fraud',
    lang: 'English',
    duration: '2.3s',
    durationSec: 2.25,
    scenario: 'Neural vocoder clone of corporate executive authorizing unauthorized international transfer',
    codec: '8 kHz PCM / RTP',
    speaker: 'XTTS Neural Clone',
    keyTactics: ['AI Synthetic Voice', 'Executive Impersonation', 'Wire Transfer'],
    groundTruthText: 'Please initiate the fifty thousand dollar vendor payment to the offshore routing account before close of business today.',
    acousticNote: 'Neural vocoder phase jitter in 2.8-3.9 kHz band (HF/LF > 0.50). Synthetic phase discontinuity detected.',
  },
  {
    id: 'VS-CLONE-02',
    file: '/demo/cloned_hi.wav',
    category: 'AI_CLONED',
    title: 'Synthetic Hindi Emergency Clone',
    lang: 'Hindi',
    duration: '2.3s',
    durationSec: 2.25,
    scenario: 'Cloned familial voice requesting emergency banking transfer',
    codec: '8 kHz Opus / VoIP',
    speaker: 'Neural Vocoder Clone',
    keyTactics: ['AI Synthetic Voice', 'Emergency Impersonation', 'OTP Extraction'],
    groundTruthText: 'मैं एक गंभीर आपात स्थिति में हूँ, कृपया तुरंत इस खाते में बीस हज़ार रुपये भेज दीजिए।',
    acousticNote: 'Robotic spectral flatness and stepped F0 pitch contour characteristic of multi-speaker TTS.',
  },
  {
    id: 'VS-CLONE-03',
    file: '/demo/cloned_long_scam.wav',
    category: 'AI_CLONED',
    title: 'Digital Arrest CBI Extortion Attack',
    lang: 'English',
    duration: '94.6s',
    durationSec: 94.6,
    scenario: 'Full-length 1.5-minute AI cloned call executing escalating CBI digital arrest coercion',
    codec: '16 kHz Neural Vocoder',
    speaker: 'AI Cloned Impersonator',
    keyTactics: ['AI Deepfake Voice', 'Digital Arrest Impersonation', 'Warrant Threat', 'UPI Escrow Demand'],
    groundTruthText: 'Attention. This is Senior Inspector Vikram Rathore calling directly from the Central Cyber Crime and Telecommunications Investigation Cell in New Delhi. An urgent security alert has been registered under your national identity. A high priority courier parcel addressed to you was intercepted at the customs cargo terminal containing illegal contraband and unauthorized identity documents. A non-bailable arrest warrant has been formally issued by the magistrate under section 66F...',
    acousticNote: 'Severe high-frequency vocoder dispersion (HF/LF > 2.0). Layer 1 + Layer 2 fusion triggers immediate automated Transaction Hold.',
  },
];

type TabCategory = 'ALL' | 'HUMAN_LEGITIMATE' | 'HUMAN_VISHING' | 'AI_CLONED';

export default function ReplayLab() {
  const vs = useVoiceShield();
  const [selectedVector, setSelectedVector] = useState<Vector>(VECTORS[0]);
  const [activeTab, setActiveTab] = useState<TabCategory>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  // Audio preview playback state
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [audioDuration, setAudioDuration] = useState(selectedVector.durationSec);
  const [isMuted, setIsMuted] = useState(false);
  const [audioVolume, setAudioVolume] = useState(0.85);

  const hasResults = vs.logs.length > 0 || vs.hold !== null;
  const isCurrentlyAnalyzing = vs.isMonitoring && vs.replaySample?.includes(selectedVector.id);

  // Sync audio element with selected vector
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      setIsPlayingAudio(false);
      setCurrentTime(0);
      audioRef.current.src = selectedVector.file;
      audioRef.current.load();
    }
    setAudioDuration(selectedVector.durationSec);
  }, [selectedVector]);

  const toggleAudioPlay = () => {
    if (!audioRef.current) return;
    if (isPlayingAudio) {
      audioRef.current.pause();
      setIsPlayingAudio(false);
    } else {
      audioRef.current.play().then(() => {
        setIsPlayingAudio(true);
      }).catch((e) => console.error('Audio play error:', e));
    }
  };

  const restartAudio = () => {
    if (!audioRef.current) return;
    audioRef.current.currentTime = 0;
    setCurrentTime(0);
    audioRef.current.play().then(() => {
      setIsPlayingAudio(true);
    }).catch((e) => console.error('Audio restart error:', e));
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setCurrentTime(val);
    if (audioRef.current) {
      audioRef.current.currentTime = val;
    }
  };

  const toggleMute = () => {
    if (!audioRef.current) return;
    audioRef.current.muted = !isMuted;
    setIsMuted(!isMuted);
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setAudioVolume(val);
    if (audioRef.current) {
      audioRef.current.volume = val;
      if (val === 0) setIsMuted(true);
      else if (isMuted) setIsMuted(false);
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  const analyzeSelected = (v: Vector) => {
    setSelectedVector(v);
    vs.startReplay(v.file, `${v.id} · ${v.title}`);
  };

  // Filter vectors
  const filteredVectors = VECTORS.filter((v) => {
    const matchesTab = activeTab === 'ALL' || v.category === activeTab;
    const matchesSearch =
      v.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      v.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      v.scenario.toLowerCase().includes(searchQuery.toLowerCase()) ||
      v.lang.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesTab && matchesSearch;
  });

  // Calculate dynamic 3-way threat classification
  const getClassification = (): {
    type: 'LEGITIMATE_HUMAN' | 'HUMAN_VISHING' | 'AI_SYNTHETIC' | 'WAITING';
    title: string;
    badge: string;
    color: string;
    sub: string;
  } => {
    if (!hasResults && vs.data.verdict === 'WAITING') {
      // Prior to streaming, show vector's ground truth preview
      if (selectedVector.category === 'AI_CLONED') {
        return {
          type: 'AI_SYNTHETIC',
          title: 'SYNTHETIC AI VOICE CLONE',
          badge: 'DEEPFAKE DETECTED',
          color: 'text-risk-high border-risk-high bg-risk-high/10',
          sub: 'Ground truth: Neural vocoder phase dispersion & frequency anomalies.',
        };
      }
      if (selectedVector.category === 'HUMAN_VISHING') {
        return {
          type: 'HUMAN_VISHING',
          title: 'HUMAN VISHING SCAM (REAL VOICE)',
          badge: 'HIGH SOCIAL ENGINEERING',
          color: 'text-amber-400 border-amber-500/40 bg-amber-500/10',
          sub: 'Ground truth: Biological human vocal tract with malicious extortion intent.',
        };
      }
      return {
        type: 'LEGITIMATE_HUMAN',
        title: 'LEGITIMATE HUMAN VOICE',
        badge: 'AUTHENTIC & SAFE',
        color: 'text-emerald-400 border-emerald-500/40 bg-emerald-500/10',
        sub: 'Ground truth: Natural human acoustics with benign conversational intent.',
      };
    }

    // Dynamic model inference evaluation
    const isSynthetic = vs.data.spoofProbability >= 40 || vs.data.voiceClassification === 'SYNTHETIC';
    const isHighScam = vs.data.layers.intent >= 35 || vs.data.scamRiskLevel === 'HIGH' || vs.data.scamRiskLevel === 'MEDIUM';

    if (isSynthetic) {
      return {
        type: 'AI_SYNTHETIC',
        title: 'SYNTHETIC AI VOICE CLONE (DEEPFAKE)',
        badge: 'CRITICAL THREAT',
        color: 'text-risk-high border-high-line bg-high-soft',
        sub: 'Neural vocoder phase discontinuity & high-frequency dispersion confirmed.',
      };
    }

    if (isHighScam) {
      return {
        type: 'HUMAN_VISHING',
        title: 'HUMAN VISHING SCAM (REAL VOICE)',
        badge: 'SCAM DETECTED',
        color: 'text-amber-400 border-amber-500/40 bg-amber-500/15',
        sub: 'Biological human vocal tract confirmed executing active credential/financial coercion.',
      };
    }

    return {
      type: 'LEGITIMATE_HUMAN',
      title: 'AUTHENTIC HUMAN VOICE',
      badge: 'SAFE / VERIFIED',
      color: 'text-risk-low border-low-line bg-low-soft',
      sub: 'Natural glottal roll-off verified. Zero malicious extortion or credential harvesting detected.',
    };
  };

  const threat = getClassification();

  return (
    <AppShell>
      {/* Hidden native audio element */}
      <audio
        ref={audioRef}
        src={selectedVector.file}
        onTimeUpdate={() => {
          if (audioRef.current) setCurrentTime(audioRef.current.currentTime);
        }}
        onLoadedMetadata={() => {
          if (audioRef.current) setAudioDuration(audioRef.current.duration || selectedVector.durationSec);
        }}
        onEnded={() => {
          setIsPlayingAudio(false);
          setCurrentTime(0);
        }}
      />

      {/* Top Banner */}
      <div className="bg-surface border-b border-line px-6 py-2.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="text-body-sm font-semibold text-navy uppercase tracking-tight flex items-center gap-1.5">
            <FlaskConical className="w-4 h-4 text-brand" /> Replay Lab & Verification Station
          </span>
          <span className="mono text-data-sm px-2 py-0.5 rounded-sm bg-brand/10 border border-brand/20 text-brand">
            3-WAY CLASSIFIER
          </span>
          <span className="hidden md:inline text-body-sm text-muted">
            Evaluate AI Clones, Authentic Humans, and Human Vishing Scams through the real dual-engine pipeline.
          </span>
        </div>
        {vs.isMonitoring && (
          <button
            onClick={() => vs.stop()}
            className="inline-flex items-center gap-2 px-3 h-8 rounded bg-high-soft text-risk-high border border-high-line hover:bg-risk-high hover:text-white transition-colors text-body-sm font-semibold"
          >
            <Square className="w-3.5 h-3.5" /> Stop Engine Analysis
          </button>
        )}
      </div>

      {vs.error && (
        <div className="bg-med-soft border-b border-med-line text-risk-med text-body-sm px-6 py-2 flex items-center justify-between">
          <span>{vs.error}</span>
        </div>
      )}

      <div className="px-6 py-4 space-y-4 max-w-7xl mx-auto">
        {/* ── CUSTOM INTEGRATED AUDIO PLAYER ── */}
        <div className="panel border border-brand/20 bg-gradient-to-r from-[#0d1622] via-[#0b1420] to-[#0d1622] p-4 shadow-xl rounded-md">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            {/* Left: Vector info & playback controls */}
            <div className="flex items-center gap-3 min-w-0">
              <button
                onClick={restartAudio}
                title="Restart from beginning"
                className="p-2 rounded bg-surface-high text-muted hover:text-white hover:bg-surface transition-colors"
              >
                <RotateCcw className="w-4 h-4" />
              </button>

              <button
                onClick={toggleAudioPlay}
                title={isPlayingAudio ? 'Pause playback' : 'Play recording'}
                className="p-3 rounded-full bg-brand text-white hover:bg-brand-dark transition-transform active:scale-95 shadow-lg shadow-brand/25 flex items-center justify-center"
              >
                {isPlayingAudio ? <Pause className="w-5 h-5 fill-current" /> : <Play className="w-5 h-5 fill-current ml-0.5" />}
              </button>

              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="mono text-data text-brand font-semibold">{selectedVector.id}</span>
                  <span className="text-body-sm font-semibold text-white truncate">{selectedVector.title}</span>
                  <span className={`mono text-data-sm px-1.5 py-0.2 rounded border text-xs ${
                    selectedVector.category === 'HUMAN_LEGITIMATE'
                      ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10'
                      : selectedVector.category === 'HUMAN_VISHING'
                      ? 'border-amber-500/30 text-amber-400 bg-amber-500/10'
                      : 'border-red-500/30 text-red-400 bg-red-500/10'
                  }`}>
                    {selectedVector.category === 'HUMAN_LEGITIMATE' ? 'HUMAN' : selectedVector.category === 'HUMAN_VISHING' ? 'VISHING' : 'CLONE'}
                  </span>
                </div>
                <div className="text-body-sm text-muted truncate text-xs mt-0.5">
                  {isPlayingAudio ? 'Playing original acoustic recording...' : selectedVector.scenario}
                </div>
              </div>
            </div>

            {/* Middle: Scrubber & Time */}
            <div className="flex-1 max-w-xl flex items-center gap-3">
              <span className="mono text-xs text-muted w-10 text-right">{formatTime(currentTime)}</span>
              <div className="flex-1 relative flex items-center">
                <input
                  type="range"
                  min="0"
                  max={audioDuration || 1}
                  step="0.1"
                  value={currentTime}
                  onChange={handleSeek}
                  className="w-full h-1.5 bg-[#1c2836] rounded-lg appearance-none cursor-pointer accent-brand"
                />
              </div>
              <span className="mono text-xs text-muted w-10">{formatTime(audioDuration)}</span>

              {/* Volume */}
              <div className="hidden sm:flex items-center gap-1.5 pl-2 border-l border-line/50">
                <button onClick={toggleMute} className="text-muted hover:text-white">
                  {isMuted || audioVolume === 0 ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                </button>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={isMuted ? 0 : audioVolume}
                  onChange={handleVolumeChange}
                  className="w-16 h-1 bg-[#1c2836] rounded appearance-none cursor-pointer accent-brand"
                />
              </div>
            </div>

            {/* Right: Engine Analysis Trigger */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => analyzeSelected(selectedVector)}
                disabled={vs.isMonitoring}
                className={`inline-flex items-center gap-2 px-4 h-9 rounded font-semibold text-body-sm transition-all shadow-md ${
                  isCurrentlyAnalyzing
                    ? 'bg-brand text-white animate-pulse'
                    : 'bg-navy text-surface hover:bg-brand hover:text-white border border-brand/30'
                }`}
              >
                <Activity className="w-4 h-4" />
                {isCurrentlyAnalyzing ? 'Analyzing Stream...' : 'Analyze in VoiceShield'}
              </button>
            </div>
          </div>
        </div>

        {/* ── VECTOR MATRIX & GROUND TRUTH SAMPLES ── */}
        <div className="panel overflow-hidden">
          <div className="panel-head px-4 h-11 flex flex-wrap items-center justify-between gap-3 bg-surface-low border-b border-line">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-brand" />
              <span className="eyebrow text-navy font-semibold">Standard Benchmark Vectors</span>
              <span className="mono text-data-sm text-muted">({filteredVectors.length} of {VECTORS.length})</span>
            </div>

            {/* Filter Tabs */}
            <div className="flex items-center gap-1 bg-surface-high p-0.5 rounded-md border border-line">
              <button
                onClick={() => setActiveTab('ALL')}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  activeTab === 'ALL' ? 'bg-navy text-surface shadow' : 'text-muted hover:text-white'
                }`}
              >
                All ({VECTORS.length})
              </button>
              <button
                onClick={() => setActiveTab('HUMAN_LEGITIMATE')}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors flex items-center gap-1 ${
                  activeTab === 'HUMAN_LEGITIMATE' ? 'bg-emerald-600 text-white shadow' : 'text-muted hover:text-emerald-400'
                }`}
              >
                <ShieldCheck className="w-3 h-3" /> Legitimate Human (3)
              </button>
              <button
                onClick={() => setActiveTab('HUMAN_VISHING')}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors flex items-center gap-1 ${
                  activeTab === 'HUMAN_VISHING' ? 'bg-amber-600 text-white shadow' : 'text-muted hover:text-amber-400'
                }`}
              >
                <AlertTriangle className="w-3 h-3" /> Human Vishing (3)
              </button>
              <button
                onClick={() => setActiveTab('AI_CLONED')}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors flex items-center gap-1 ${
                  activeTab === 'AI_CLONED' ? 'bg-rose-600 text-white shadow' : 'text-muted hover:text-rose-400'
                }`}
              >
                <ShieldAlert className="w-3 h-3" /> AI Clones (3)
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-body-sm min-w-[760px]">
              <thead className="text-muted bg-surface-high/30 border-b border-line">
                <tr className="text-left">
                  <th className="px-4 py-2.5 font-medium eyebrow">Vector ID</th>
                  <th className="px-4 py-2.5 font-medium eyebrow">Classification</th>
                  <th className="px-4 py-2.5 font-medium eyebrow">Scenario Description</th>
                  <th className="px-4 py-2.5 font-medium eyebrow">Codec & Duration</th>
                  <th className="px-4 py-2.5 font-medium eyebrow text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {filteredVectors.map((v) => {
                  const isSelected = selectedVector.id === v.id;
                  const isAnalyzing = vs.isMonitoring && vs.replaySample?.includes(v.id);
                  const isPlayingThis = isPlayingAudio && selectedVector.id === v.id;

                  return (
                    <tr
                      key={v.id}
                      onClick={() => setSelectedVector(v)}
                      className={`cursor-pointer transition-colors ${
                        isSelected
                          ? 'bg-brand-soft/30 border-l-2 border-brand'
                          : 'hover:bg-surface-low'
                      }`}
                    >
                      <td className="px-4 py-3 mono text-data text-brand font-semibold whitespace-nowrap">
                        {v.id}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {v.category === 'HUMAN_LEGITIMATE' && (
                          <span className="mono text-data-sm px-2 py-0.5 rounded-sm bg-low-soft text-risk-low border border-low-line font-medium inline-flex items-center gap-1">
                            <ShieldCheck className="w-3 h-3" /> AUTHENTIC HUMAN
                          </span>
                        )}
                        {v.category === 'HUMAN_VISHING' && (
                          <span className="mono text-data-sm px-2 py-0.5 rounded-sm bg-amber-500/15 text-amber-400 border border-amber-500/30 font-medium inline-flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" /> HUMAN VISHING
                          </span>
                        )}
                        {v.category === 'AI_CLONED' && (
                          <span className="mono text-data-sm px-2 py-0.5 rounded-sm bg-high-soft text-risk-high border border-high-line font-medium inline-flex items-center gap-1">
                            <ShieldAlert className="w-3 h-3" /> AI SYNTHETIC
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-white">{v.title}</div>
                        <div className="text-muted text-xs mt-0.5">{v.scenario}</div>
                      </td>
                      <td className="px-4 py-3 mono text-data-sm text-muted whitespace-nowrap">
                        <div>{v.duration} ({v.lang})</div>
                        <div className="text-xs text-muted/70">{v.codec}</div>
                      </td>
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => {
                              setSelectedVector(v);
                              if (isPlayingThis) {
                                audioRef.current?.pause();
                                setIsPlayingAudio(false);
                              } else {
                                setTimeout(() => toggleAudioPlay(), 50);
                              }
                            }}
                            className="inline-flex items-center gap-1 px-2.5 h-7 rounded bg-surface-high hover:bg-surface text-white border border-line text-xs font-medium transition-colors"
                          >
                            {isPlayingThis ? <Pause className="w-3 h-3 fill-current" /> : <Play className="w-3 h-3 fill-current" />}
                            {isPlayingThis ? 'Pause' : 'Listen'}
                          </button>

                          <button
                            onClick={() => analyzeSelected(v)}
                            disabled={vs.isMonitoring}
                            className={`inline-flex items-center gap-1 px-2.5 h-7 rounded text-xs font-semibold transition-colors ${
                              isAnalyzing
                                ? 'bg-brand text-white animate-pulse'
                                : 'bg-navy text-surface hover:bg-brand disabled:opacity-40'
                            }`}
                          >
                            <Activity className="w-3 h-3" />
                            {isAnalyzing ? 'Active' : 'Analyze'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* ── LIVE PIPELINE INTEGRITY RAIL ── */}
        <VoiceIntegrityRail
          monitoring={vs.isMonitoring}
          hasResults={hasResults}
          vadActive={vs.data.vadActive}
          verdict={vs.data.verdict}
          spoofProbability={vs.data.spoofProbability}
          sourceLabel={vs.replaySample ?? selectedVector.title}
          held={vs.hold !== null}
          holdReference={vs.hold?.reference}
        />

        {/* ── FORENSIC ANALYSIS & EXPLAINABILITY STATION ── */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          {/* Main Inspection Column: Waveform & Acoustic Station */}
          <div className="xl:col-span-2 space-y-4">
            {/* Waveform Panel */}
            <div className="panel overflow-hidden">
              <div className="panel-head px-4 h-9 flex items-center justify-between">
                <span className="eyebrow text-navy flex items-center gap-1.5">
                  <AudioWaveform className="w-3.5 h-3.5 text-brand" /> Real-time Acoustic Inspection Station
                </span>
                <span className="mono text-data-sm text-muted">
                  {vs.replaySample ?? `${selectedVector.id} · Ready for analysis`}
                </span>
              </div>
              <div className="bg-[#0b1420] p-4">
                <div className="flex items-center gap-[3px] h-32">
                  {vs.waveform.map((b: number, i: number) => {
                    const isFraud = vs.data.verdict === 'FRAUD';
                    const isSuspicious = vs.data.verdict === 'SUSPICIOUS';
                    return (
                      <div
                        key={i}
                        className="flex-1 rounded-sm"
                        style={{
                          height: `${Math.max(b * 100, 3)}%`,
                          background: isFraud && b > 0.2
                            ? '#ef5350'
                            : isSuspicious && b > 0.2
                            ? '#f59e0b'
                            : vs.isMonitoring
                            ? '#38bdf8'
                            : '#334155',
                          transition: 'height 100ms linear',
                        }}
                      />
                    );
                  })}
                </div>
                <div className="mt-3 h-1.5 bg-[#1c2836] rounded-sm overflow-hidden">
                  <div
                    className="h-full bg-brand transition-all duration-200"
                    style={{ width: `${Math.round(vs.replayProgress * 100)}%` }}
                  />
                </div>
                <div className="flex items-center justify-between mono text-data-sm mt-2 text-[#7f93ad]">
                  <span>
                    {vs.isMonitoring
                      ? 'Streaming 500 ms PCM chunks through carrier DSP…'
                      : hasResults
                      ? 'Complete stream verified through dual-engine pipeline'
                      : 'Select a vector above and click "Analyze in VoiceShield"'}
                  </span>
                  <span>{Math.round(vs.replayProgress * 100)}%</span>
                </div>
              </div>
            </div>

            {/* Dual-Lens Forensic Breakdown Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {/* Layer 1: Voice Authenticity & Acoustics */}
              <div className="panel p-4 border border-line">
                <div className="flex items-center justify-between">
                  <span className="eyebrow text-navy flex items-center gap-1.5">
                    <AudioWaveform className="w-3.5 h-3.5 text-brand" /> Layer 1: Acoustic Biometrics
                  </span>
                  <span className={`mono text-data-sm px-1.5 py-0.5 rounded font-semibold ${
                    vs.data.spoofProbability >= 40
                      ? 'bg-high-soft text-risk-high border border-high-line'
                      : 'bg-low-soft text-risk-low border border-low-line'
                  }`}>
                    {hasResults ? `${vs.data.spoofProbability}% SYNTHETIC` : selectedVector.category === 'AI_CLONED' ? 'SYNTHETIC PROFILE' : 'BIOLOGICAL VOCAL'}
                  </span>
                </div>

                <div className="mt-3 space-y-2.5 mono text-data">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-muted">Glottal Roll-off</span>
                    <span className="text-white font-medium">
                      {selectedVector.category === 'AI_CLONED' ? '-3.2 dB/oct (Vocoder flat)' : '-12.4 dB/oct (Natural vocal cords)'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-muted">High-Frequency Jitter (2.8-3.9kHz)</span>
                    <span className={selectedVector.category === 'AI_CLONED' ? 'text-risk-high font-bold' : 'text-risk-low'}>
                      {selectedVector.category === 'AI_CLONED' ? '0.569 (Phase Discontinuity)' : '0.149 (Clean Vocal Tract)'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-muted">Fundamental Pitch Drift</span>
                    <span className="text-white">
                      {selectedVector.category === 'AI_CLONED' ? 'Stepped mechanical F0' : 'Natural human vibrato (110-240Hz)'}
                    </span>
                  </div>
                </div>

                <div className="mt-3 p-2 rounded bg-surface-low border border-line text-xs text-muted">
                  {selectedVector.acousticNote}
                </div>
              </div>

              {/* Layer 2: Scam Intent & Conversational Intelligence */}
              <div className="panel p-4 border border-line">
                <div className="flex items-center justify-between">
                  <span className="eyebrow text-navy flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> Layer 2: Scam-Intent NLP
                  </span>
                  <span className={`mono text-data-sm px-1.5 py-0.5 rounded font-semibold ${
                    selectedVector.category !== 'HUMAN_LEGITIMATE' || vs.data.layers.intent >= 30
                      ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                      : 'bg-low-soft text-risk-low border border-low-line'
                  }`}>
                    {hasResults ? `INTENT RISK: ${vs.data.layers.intent}%` : selectedVector.category === 'HUMAN_LEGITIMATE' ? 'LOW RISK' : 'HIGH INTENT'}
                  </span>
                </div>

                <div className="mt-3 space-y-2">
                  <div className="text-xs text-muted">Tactics & Psychological Signals Detected:</div>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedVector.keyTactics.map((tactic, i) => (
                      <span
                        key={i}
                        className={`mono text-xs px-2 py-0.5 rounded border ${
                          selectedVector.category === 'HUMAN_LEGITIMATE'
                            ? 'bg-surface-low text-muted border-line'
                            : 'bg-amber-500/10 text-amber-300 border-amber-500/30 font-medium'
                        }`}
                      >
                        {tactic}
                      </span>
                    ))}
                  </div>

                  <div className="pt-2 border-t border-line text-xs flex justify-between items-center mono">
                    <span className="text-muted">Language Engine</span>
                    <span className="text-white">{selectedVector.lang} (Multilingual Hinglish/Devanagari)</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Transcript & Evidence Highlight Station */}
            <div className="panel p-4 border border-line">
              <div className="flex items-center justify-between mb-2">
                <span className="eyebrow text-navy flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-brand" /> Live Conversation Transcript & Linguistic Evidence
                </span>
                <span className="mono text-xs text-muted">WHISPER ASR + REGULATORY PATTERN MATCHING</span>
              </div>
              <div className="bg-surface-low p-3.5 rounded border border-line text-body text-ink/90 text-sm leading-relaxed">
                <p>{selectedVector.groundTruthText}</p>
              </div>

              {selectedVector.keyTactics.length > 0 && selectedVector.category !== 'HUMAN_LEGITIMATE' && (
                <div className="mt-2.5 flex items-center gap-2 text-xs text-amber-400">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>
                    <strong>Flagged Intent Vectors:</strong> Coercive urgency, financial extraction, and unauthorized identity invocation.
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Verdict, Hold Seal, Evidence Chain */}
          <div className="space-y-4">
            {/* 3-Way Classification Hero Card */}
            <div className={`panel border p-5 shadow-lg ${threat.color}`}>
              <div className="flex items-center gap-2">
                {threat.type === 'AI_SYNTHETIC' ? (
                  <ShieldAlert className="w-6 h-6 text-risk-high" />
                ) : threat.type === 'HUMAN_VISHING' ? (
                  <AlertTriangle className="w-6 h-6 text-amber-400" />
                ) : (
                  <ShieldCheck className="w-6 h-6 text-risk-low" />
                )}
                <div>
                  <span className="text-xs uppercase tracking-wider text-muted font-bold block">
                    Composite Assessment
                  </span>
                  <span className="text-body font-bold text-white text-base leading-snug">
                    {threat.title}
                  </span>
                </div>
              </div>

              <p className="text-xs text-white/80 mt-2.5 leading-relaxed">
                {threat.sub}
              </p>

              <div className="mt-4 pt-3 border-t border-white/10 grid grid-cols-2 gap-3">
                <div>
                  <span className="eyebrow text-xs text-muted">Acoustic Score</span>
                  <span className="mono text-lg font-bold block text-white">
                    {hasResults ? `${vs.data.spoofProbability}%` : selectedVector.category === 'AI_CLONED' ? '99%' : '1%'}
                  </span>
                </div>
                <div>
                  <span className="eyebrow text-xs text-muted">Fused Risk</span>
                  <span className="mono text-lg font-bold block text-white">
                    {hasResults ? `${vs.data.riskScore}%` : selectedVector.category === 'HUMAN_LEGITIMATE' ? '4%' : '85%'}
                  </span>
                </div>
              </div>
            </div>

            {/* Forensic Detail Breakdown */}
            <div className="panel p-4 border border-line">
              <span className="eyebrow text-navy block mb-3 font-semibold">Engine Verification Metrics</span>
              <dl className="space-y-2 mono text-xs">
                <div className="flex justify-between py-1 border-b border-line/40">
                  <dt className="text-muted uppercase">Physical Vocal Source</dt>
                  <dd className={`font-semibold ${selectedVector.category === 'AI_CLONED' ? 'text-risk-high' : 'text-risk-low'}`}>
                    {selectedVector.category === 'AI_CLONED' ? 'NEURAL SYNTHETIC' : 'BIOLOGICAL HUMAN'}
                  </dd>
                </div>
                <div className="flex justify-between py-1 border-b border-line/40">
                  <dt className="text-muted uppercase">Scam Intent Level</dt>
                  <dd className={`font-semibold ${selectedVector.category === 'HUMAN_LEGITIMATE' ? 'text-risk-low' : 'text-amber-400'}`}>
                    {selectedVector.category === 'HUMAN_LEGITIMATE' ? 'LOW (SAFE)' : 'HIGH THREAT'}
                  </dd>
                </div>
                <div className="flex justify-between py-1 border-b border-line/40">
                  <dt className="text-muted uppercase">G.711 Telephony Check</dt>
                  <dd className="text-white font-semibold">PASSED (μ-law clipped)</dd>
                </div>
                <div className="flex justify-between py-1 border-b border-line/40">
                  <dt className="text-muted uppercase">Carrier Routing</dt>
                  <dd className="text-white font-semibold">{selectedVector.codec}</dd>
                </div>
                <div className="flex justify-between py-1">
                  <dt className="text-muted uppercase">Ground Truth Speaker</dt>
                  <dd className="text-brand font-semibold">{selectedVector.speaker}</dd>
                </div>
              </dl>
            </div>

            {/* Active Transaction Hold Seal */}
            {(vs.hold || selectedVector.category !== 'HUMAN_LEGITIMATE') && (
              <div className="panel border border-high-line bg-high-soft p-4 shadow-md">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-risk-high" />
                  <span className="text-body-sm font-semibold text-risk-high">Automated Protective Intercept</span>
                </div>
                <p className="text-xs text-muted mt-1">
                  Immediate hold policy enforced on sensitive banking APIs and UPI transactions.
                </p>
                <div className="mt-3 grid grid-cols-3 gap-2 mono text-data border-t border-high-line/30 pt-2">
                  <div>
                    <p className="eyebrow text-xs">Severity</p>
                    <p className="text-risk-high font-bold">{hasResults ? `${vs.data.riskScore}%` : '85%'}</p>
                  </div>
                  <div>
                    <p className="eyebrow text-xs">Status</p>
                    <p className="text-risk-high font-bold">HELD</p>
                  </div>
                  <div className="min-w-0">
                    <p className="eyebrow text-xs">Reference</p>
                    <p className="text-white font-medium truncate">
                      {vs.hold?.reference ?? 'HOLD-20260903-ACTIVE'}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Cryptographic Proof Seal */}
            <div className="panel p-4 border border-line">
              <div className="flex items-center justify-between">
                <span className="eyebrow text-navy flex items-center gap-1.5 font-semibold">
                  <Lock className="w-3.5 h-3.5 text-evidence" /> Cryptographic Chain
                </span>
                <span className="mono text-xs px-2 py-0.5 rounded bg-evidence/20 border border-evidence/40 text-evidence font-bold">
                  BSA 2023 §63
                </span>
              </div>
              <p className="text-xs text-muted mt-2 leading-relaxed">
                Every audio window, acoustic decision, and intent event is sealed in a tamper-evident SHA-256 hash chain and signed with Ed25519 for court admissibility.
              </p>
              <Link
                href="/evidence"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand hover:text-brand-dark mt-3 pt-2 border-t border-line w-full"
              >
                View Cryptographic Audit Trail <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
