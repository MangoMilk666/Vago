import React, { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { sendSmsCode, loginByPhone, register } from '../api/user'
import { saveAuth } from '../stores/auth'

// ─── 图标 SVG（轻量内联，避免引入 icon 库）─────────────────────────────────────
const IconPhone = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
      d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13
         a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0
         01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
  </svg>
)

const IconShield = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
      d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0
         01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622
         5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
  </svg>
)

const IconUser = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
      d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
  </svg>
)

const IconMapPin = () => (
  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243
         a8 8 0 1111.314 0z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
)

// ─── 步骤枚举 ─────────────────────────────────────────────────────────────────
const STEP = { PHONE: 'phone', CODE: 'code', NICKNAME: 'nickname' }

// ─── 倒计时 Hook ─────────────────────────────────────────────────────────────
function useCountdown(seconds = 60) {
  const [count, setCount] = useState(0)
  const timer = useRef(null)

  const start = () => {
    setCount(seconds)
    timer.current = setInterval(() => {
      setCount((c) => {
        if (c <= 1) {
          clearInterval(timer.current)
          return 0
        }
        return c - 1
      })
    }, 1000)
  }

  useEffect(() => () => clearInterval(timer.current), [])
  return { count, start, running: count > 0 }
}

// ─── 主组件 ───────────────────────────────────────────────────────────────────
export default function LoginPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState(STEP.PHONE)
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [nickname, setNickname] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [isNewUser, setIsNewUser] = useState(false)
  const countdown = useCountdown(60)

  const clearError = () => setError('')

  // ── 验证手机号格式 ───────────────────────────────────────────────────────────
  const isValidPhone = /^1[3-9]\d{9}$/.test(phone)

  // ── 发送验证码 ───────────────────────────────────────────────────────────────
  const handleSendCode = async () => {
    if (!isValidPhone || countdown.running) return
    clearError()
    setLoading(true)
    try {
      await sendSmsCode(phone)
      countdown.start()
      setStep(STEP.CODE)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // ── 验证码登录/注册 ──────────────────────────────────────────────────────────
  const handleVerifyCode = async () => {
    if (code.length !== 6) {
      setError('请输入 6 位验证码')
      return
    }
    clearError()
    setLoading(true)
    try {
      // 先尝试登录
      const res = await loginByPhone(phone, code)
      if (res.code === 200) {
        handleLoginSuccess(res.data)
      }
    } catch (err) {
      // 4090 = 用户不存在，需要注册
      if (err.message?.includes('不存在') || err.message?.includes('4090')) {
        setIsNewUser(true)
        setStep(STEP.NICKNAME)
      } else {
        setError(err.message)
      }
    } finally {
      setLoading(false)
    }
  }

  // ── 完成注册 ─────────────────────────────────────────────────────────────────
  const handleRegister = async () => {
    if (!nickname.trim() || nickname.length < 2) {
      setError('昵称至少 2 个字符')
      return
    }
    clearError()
    setLoading(true)
    try {
      const res = await register(phone, code, nickname.trim())
      if (res.code === 200) {
        handleLoginSuccess(res.data)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // ── 登录成功处理 ─────────────────────────────────────────────────────────────
  const handleLoginSuccess = (data) => {
    saveAuth({
      accessToken: data.accessToken,
      refreshToken: data.refreshToken,
      user: data.user,
    })
    localStorage.setItem('accessToken', data.accessToken)
    localStorage.setItem('refreshToken', data.refreshToken)
    navigate('/')
  }

  // ── 回到上一步 ───────────────────────────────────────────────────────────────
  const goBack = () => {
    clearError()
    setCode('')
    setStep(step === STEP.NICKNAME ? STEP.CODE : STEP.PHONE)
  }

  // ─── 步骤标题 & 描述 ──────────────────────────────────────────────────────────
  const stepMeta = {
    [STEP.PHONE]:    { title: '欢迎回来', sub: '输入手机号登录或注册叠迹' },
    [STEP.CODE]:     { title: '验证身份', sub: `验证码已发送至 ${phone}` },
    [STEP.NICKNAME]: { title: '起个昵称', sub: '这是你在叠迹上的专属身份' },
  }

  return (
    <div className="min-h-screen flex">
      {/* ── 左侧装饰面板（大屏显示）─────────────────────────────────────── */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12
                      bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-500
                      text-white relative overflow-hidden">
        {/* 背景装饰圆 */}
        <div className="absolute -top-32 -left-32 w-80 h-80 bg-white/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-20 -right-20 w-72 h-72 bg-white/10 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/3 w-40 h-40 bg-pink-300/20 rounded-full blur-2xl" />

        {/* Logo */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="w-10 h-10 bg-white/20 rounded-2xl flex items-center justify-center backdrop-blur-sm">
            <IconMapPin />
          </div>
          <span className="text-2xl font-bold tracking-tight">叠迹 Vago</span>
        </div>

        {/* 主宣传语 */}
        <div className="relative z-10 space-y-6">
          <h1 className="text-5xl font-bold leading-tight">
            记录你<br />
            走过的<br />
            <span className="text-yellow-300">每一步</span>
          </h1>
          <p className="text-lg text-white/80 leading-relaxed max-w-sm">
            足迹地图 · AI 行程规划 · 图文攻略库<br />
            让旅行的记忆有迹可循
          </p>

          {/* 特性标签 */}
          <div className="flex flex-wrap gap-2 pt-2">
            {['足迹热力图', 'AI 规划', '攻略分享', '迷雾探索'].map((tag) => (
              <span key={tag}
                className="px-3 py-1.5 bg-white/15 backdrop-blur-sm rounded-full text-sm font-medium">
                {tag}
              </span>
            ))}
          </div>
        </div>

        {/* 底部用户数据 */}
        <div className="relative z-10 flex gap-8 text-sm">
          <div>
            <div className="text-2xl font-bold">10K+</div>
            <div className="text-white/70 mt-0.5">活跃旅行者</div>
          </div>
          <div>
            <div className="text-2xl font-bold">50+</div>
            <div className="text-white/70 mt-0.5">城市覆盖</div>
          </div>
          <div>
            <div className="text-2xl font-bold">200K+</div>
            <div className="text-white/70 mt-0.5">足迹记录</div>
          </div>
        </div>
      </div>

      {/* ── 右侧登录表单 ──────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 bg-gray-50">
        {/* 移动端 Logo */}
        <div className="lg:hidden flex items-center gap-2 mb-10">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600
                          flex items-center justify-center text-white">
            <IconMapPin />
          </div>
          <span className="text-xl font-bold text-gray-900">叠迹 Vago</span>
        </div>

        {/* 登录卡片 */}
        <div className="w-full max-w-md animate-slide-up">
          <div className="bg-white rounded-3xl shadow-xl shadow-gray-200/80 p-8 md:p-10">

            {/* 步骤头部 */}
            <div className="mb-8">
              {step !== STEP.PHONE && (
                <button onClick={goBack}
                  className="mb-4 flex items-center gap-1.5 text-sm text-gray-400
                             hover:text-gray-700 transition-colors">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M15 19l-7-7 7-7" />
                  </svg>
                  返回
                </button>
              )}
              <h2 className="text-2xl font-bold text-gray-900">
                {stepMeta[step].title}
              </h2>
              <p className="mt-1.5 text-sm text-gray-500">{stepMeta[step].sub}</p>
            </div>

            {/* ── Step 1: 手机号 ─────────────────────────────────────────── */}
            {step === STEP.PHONE && (
              <div className="space-y-4 animate-fade-in">
                <div className="relative">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400">
                    <IconPhone />
                  </div>
                  <input
                    type="tel"
                    inputMode="numeric"
                    maxLength={11}
                    placeholder="请输入手机号"
                    value={phone}
                    onChange={(e) => {
                      setPhone(e.target.value.replace(/\D/g, ''))
                      clearError()
                    }}
                    onKeyDown={(e) => e.key === 'Enter' && handleSendCode()}
                    className="input-base pl-11"
                  />
                </div>

                {error && <ErrorTip msg={error} />}

                <button
                  onClick={handleSendCode}
                  disabled={!isValidPhone || loading}
                  className="btn-primary"
                >
                  {loading ? <Spinner /> : '获取验证码'}
                </button>

                <p className="text-center text-xs text-gray-400 pt-2">
                  登录即代表同意{' '}
                  <a href="#" className="text-indigo-500 hover:underline">用户协议</a>
                  {' '}与{' '}
                  <a href="#" className="text-indigo-500 hover:underline">隐私政策</a>
                </p>
              </div>
            )}

            {/* ── Step 2: 验证码 ─────────────────────────────────────────── */}
            {step === STEP.CODE && (
              <div className="space-y-4 animate-fade-in">
                <div className="relative">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400">
                    <IconShield />
                  </div>
                  <input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="输入 6 位验证码"
                    value={code}
                    onChange={(e) => {
                      setCode(e.target.value.replace(/\D/g, ''))
                      clearError()
                    }}
                    onKeyDown={(e) => e.key === 'Enter' && handleVerifyCode()}
                    className="input-base pl-11 tracking-[0.25em] font-mono text-base"
                    autoFocus
                  />
                </div>

                {error && <ErrorTip msg={error} />}

                <button
                  onClick={handleVerifyCode}
                  disabled={code.length !== 6 || loading}
                  className="btn-primary"
                >
                  {loading ? <Spinner /> : '验证并登录'}
                </button>

                {/* 重发验证码 */}
                <div className="text-center">
                  {countdown.running ? (
                    <span className="text-sm text-gray-400">
                      {countdown.count}s 后可重新发送
                    </span>
                  ) : (
                    <button
                      onClick={handleSendCode}
                      disabled={loading}
                      className="text-sm text-indigo-500 hover:text-indigo-700 transition-colors"
                    >
                      重新发送验证码
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* ── Step 3: 昵称（新用户）──────────────────────────────────── */}
            {step === STEP.NICKNAME && (
              <div className="space-y-4 animate-fade-in">
                {/* 新用户提示 */}
                <div className="flex items-center gap-2.5 bg-indigo-50 rounded-xl p-3.5">
                  <span className="text-2xl">👋</span>
                  <div>
                    <p className="text-sm font-medium text-indigo-900">首次登录叠迹</p>
                    <p className="text-xs text-indigo-600 mt-0.5">给自己起一个旅行昵称吧</p>
                  </div>
                </div>

                <div className="relative">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400">
                    <IconUser />
                  </div>
                  <input
                    type="text"
                    maxLength={20}
                    placeholder="昵称（2-20 字符）"
                    value={nickname}
                    onChange={(e) => {
                      setNickname(e.target.value)
                      clearError()
                    }}
                    onKeyDown={(e) => e.key === 'Enter' && handleRegister()}
                    className="input-base pl-11"
                    autoFocus
                  />
                </div>

                {error && <ErrorTip msg={error} />}

                <button
                  onClick={handleRegister}
                  disabled={nickname.trim().length < 2 || loading}
                  className="btn-primary"
                >
                  {loading ? <Spinner /> : '开始我的旅程'}
                </button>
              </div>
            )}
          </div>

          {/* 步骤指示器 */}
          <div className="flex justify-center gap-1.5 mt-6">
            {Object.values(STEP).map((s) => (
              <div key={s}
                className={`h-1 rounded-full transition-all duration-300
                  ${s === step ? 'w-6 bg-indigo-500' : 'w-1.5 bg-gray-300'}`}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── 小组件 ───────────────────────────────────────────────────────────────────
function ErrorTip({ msg }) {
  return (
    <div className="flex items-center gap-2 bg-red-50 border border-red-100
                    rounded-xl px-3.5 py-2.5">
      <svg className="w-4 h-4 text-red-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd"
          d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1
             0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
      </svg>
      <span className="text-sm text-red-600">{msg}</span>
    </div>
  )
}

function Spinner() {
  return (
    <svg className="animate-spin h-5 w-5 text-white mx-auto" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10"
        stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}
