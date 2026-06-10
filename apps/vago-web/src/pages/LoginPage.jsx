import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { sendSmsCode, loginByPhone, loginByOAuth } from '../api/user'
import { saveAuth } from '../stores/auth'

// ─── 图标 SVG ─────────────────────────────────────────────────────────────────
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

const IconMapPin = () => (
  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
      d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
)

const IconGithub = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 .5C5.65.5.5 5.66.5 12.02c0 5.09 3.29 9.4 7.86 10.92.58.11.79-.25.79-.56v-2.16c-3.2.7-3.88-1.38-3.88-1.38-.52-1.34-1.28-1.69-1.28-1.69-1.05-.72.08-.71.08-.71 1.16.08 1.77 1.2 1.77 1.2 1.04 1.78 2.72 1.27 3.38.97.1-.75.4-1.27.73-1.56-2.55-.29-5.23-1.28-5.23-5.67 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.48.11-3.08 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.78 0c2.19-1.49 3.16-1.18 3.16-1.18.63 1.6.23 2.79.11 3.08.74.81 1.19 1.84 1.19 3.1 0 4.4-2.68 5.38-5.24 5.67.41.36.78 1.08.78 2.18v3.22c0 .31.21.67.8.56 4.56-1.52 7.85-5.83 7.85-10.92C23.5 5.66 18.35.5 12 .5Z" />
  </svg>
)

// ─── 步骤枚举（仅两步）────────────────────────────────────────────────────────
const STEP = { PHONE: 'phone', CODE: 'code' }
const GITHUB_OAUTH_STATE_KEY = 'vago:oauth:github:state'
const GITHUB_CLIENT_ID = import.meta.env.VITE_GITHUB_CLIENT_ID

function getGithubRedirectUri() {
  return import.meta.env.VITE_GITHUB_REDIRECT_URI || `${window.location.origin}/login`
}

function generateOAuthState() {
  return window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function buildGithubAuthorizeUrl() {
  const redirectUri = getGithubRedirectUri()
  const state = generateOAuthState()
  sessionStorage.setItem(GITHUB_OAUTH_STATE_KEY, state)

  const params = new URLSearchParams({
    client_id: GITHUB_CLIENT_ID,
    redirect_uri: redirectUri,
    scope: 'read:user user:email',
    state,
  })

  return `https://github.com/login/oauth/authorize?${params.toString()}`
}

// ─── 倒计时 Hook ──────────────────────────────────────────────────────────────
function useCountdown(seconds = 60) {
  const [count, setCount] = useState(0)
  const timer = useRef(null)

  const start = () => {
    setCount(seconds)
    timer.current = setInterval(() => {
      setCount((c) => {
        if (c <= 1) { clearInterval(timer.current); return 0 }
        return c - 1
      })
    }, 1000)
  }

  useEffect(() => () => clearInterval(timer.current), [])
  return { count, start, running: count > 0 }
}

// ─── 主组件 ───────────────────────────────────────────────────────────────────
export default function LoginPage() {
  const navigate  = useNavigate()
  const [step,    setStep]    = useState(STEP.PHONE)
  const [phone,   setPhone]   = useState('')
  const [code,    setCode]    = useState('')
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')
  const countdown = useCountdown(60)
  const oauthCallbackKeyRef = useRef('')

  const isValidPhone = /^1[3-9]\d{9}$/.test(phone)
  const githubEnabled = Boolean(GITHUB_CLIENT_ID)

  const handleLoginSuccess = (res) => {
    if (res.code !== 200) return
    const { accessToken, refreshToken, userInfo } = res.data
    saveAuth({ accessToken, refreshToken, user: userInfo })
    localStorage.setItem('accessToken', accessToken)
    localStorage.setItem('refreshToken', refreshToken)
    navigate('/')
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const githubCode = params.get('code')
    const githubError = params.get('error')
    const githubState = params.get('state')

    if (!githubCode && !githubError) return

    const callbackKey = `${githubCode || ''}:${githubError || ''}:${githubState || ''}`
    if (oauthCallbackKeyRef.current === callbackKey) {
      return
    }
    oauthCallbackKeyRef.current = callbackKey

    window.history.replaceState({}, document.title, '/login')

    if (githubError) {
      sessionStorage.removeItem(GITHUB_OAUTH_STATE_KEY)
      setError('GitHub 授权已取消，请重试')
      return
    }

    const storedState = sessionStorage.getItem(GITHUB_OAUTH_STATE_KEY)
    if (!githubState || !storedState || githubState !== storedState) {
      sessionStorage.removeItem(GITHUB_OAUTH_STATE_KEY)
      setError('GitHub 登录状态校验失败，请重新发起登录')
      return
    }

    const doGithubLogin = async () => {
      setError('')
      setLoading(true)
      try {
        const res = await loginByOAuth('github', githubCode, getGithubRedirectUri())
        handleLoginSuccess(res)
      } catch (err) {
        setError(err.message)
      } finally {
        sessionStorage.removeItem(GITHUB_OAUTH_STATE_KEY)
        setLoading(false)
      }
    }

    doGithubLogin()
  }, [navigate])

  // ── 发送验证码 ───────────────────────────────────────────────────────────────
  const handleSendCode = async () => {
    if (!isValidPhone || countdown.running) return
    setError(''); setLoading(true)
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

  // ── 验证码登录（新手机号后端自动注册）──────────────────────────────────────
  const handleVerifyCode = async () => {
    if (code.length !== 6) { setError('请输入 6 位验证码'); return }
    setError(''); setLoading(true)
    try {
      const res = await loginByPhone(phone, code)
      handleLoginSuccess(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleGitHubLogin = () => {
    if (!githubEnabled || loading) return
    setError('')
    window.location.href = buildGithubAuthorizeUrl()
  }

  const goBack = () => { setError(''); setCode(''); setStep(STEP.PHONE) }

  const stepMeta = {
    [STEP.PHONE]: { title: '欢迎回来', sub: '输入手机号登录，新用户自动注册' },
    [STEP.CODE]:  { title: '验证身份', sub: `验证码已发送至 ${phone}` },
  }

  return (
    <div className="min-h-screen flex">
      {/* ── 左侧装饰面板 ──────────────────────────────────────────────────── */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12
                      bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-500
                      text-white relative overflow-hidden">
        <div className="absolute -top-32 -left-32 w-80 h-80 bg-white/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-20 -right-20 w-72 h-72 bg-white/10 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/3 w-40 h-40 bg-pink-300/20 rounded-full blur-2xl" />

        <div className="relative z-10 flex items-center gap-3">
          <div className="w-10 h-10 bg-white/20 rounded-2xl flex items-center justify-center backdrop-blur-sm">
            <IconMapPin />
          </div>
          <span className="text-2xl font-bold tracking-tight">叠迹 Vago</span>
        </div>

        <div className="relative z-10 space-y-6">
          <h1 className="text-5xl font-bold leading-tight">
            记录你<br />走过的<br /><span className="text-yellow-300">每一步</span>
          </h1>
          <p className="text-lg text-white/80 leading-relaxed max-w-sm">
            足迹地图 · AI 行程规划 · 图文攻略库<br />让旅行的记忆有迹可循
          </p>
          <div className="flex flex-wrap gap-2 pt-2">
            {['足迹热力图', 'AI 规划', '攻略分享', '迷雾探索'].map((tag) => (
              <span key={tag}
                className="px-3 py-1.5 bg-white/15 backdrop-blur-sm rounded-full text-sm font-medium">
                {tag}
              </span>
            ))}
          </div>
        </div>

        <div className="relative z-10 flex gap-8 text-sm">
          {[['10K+', '活跃旅行者'], ['50+', '城市覆盖'], ['200K+', '足迹记录']].map(([num, label]) => (
            <div key={label}>
              <div className="text-2xl font-bold">{num}</div>
              <div className="text-white/70 mt-0.5">{label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── 右侧登录表单 ──────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 bg-gray-50">
        <div className="lg:hidden flex items-center gap-2 mb-10">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600
                          flex items-center justify-center text-white">
            <IconMapPin />
          </div>
          <span className="text-xl font-bold text-gray-900">叠迹 Vago</span>
        </div>

        <div className="w-full max-w-md">
          <div className="bg-white rounded-3xl shadow-xl shadow-gray-200/80 p-8 md:p-10">

            {/* 步骤头部 */}
            <div className="mb-8">
              {step === STEP.CODE && (
                <button onClick={goBack}
                  className="mb-4 flex items-center gap-1.5 text-sm text-gray-400
                             hover:text-gray-700 transition-colors">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/>
                  </svg>
                  返回
                </button>
              )}
              <h2 className="text-2xl font-bold text-gray-900">{stepMeta[step].title}</h2>
              <p className="mt-1.5 text-sm text-gray-500">{stepMeta[step].sub}</p>
            </div>

            {/* Step 1: 手机号 */}
            {step === STEP.PHONE && (
              <div className="space-y-4">
                <div className="relative">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400">
                    <IconPhone />
                  </div>
                  <input type="tel" inputMode="numeric" maxLength={11}
                    placeholder="请输入手机号"
                    value={phone}
                    onChange={(e) => { setPhone(e.target.value.replace(/\D/g, '')); setError('') }}
                    onKeyDown={(e) => e.key === 'Enter' && handleSendCode()}
                    className="w-full rounded-2xl border border-gray-200 bg-gray-50 pl-11 pr-4
                               py-3.5 text-sm outline-none focus:border-indigo-400 focus:ring-2
                               focus:ring-indigo-100 transition-all"/>
                </div>

                {error && <ErrorTip msg={error}/>}

                <button onClick={handleSendCode} disabled={!isValidPhone || loading}
                  className="w-full py-3.5 bg-indigo-600 text-white font-semibold rounded-2xl
                             hover:bg-indigo-700 disabled:opacity-40 transition-colors text-sm">
                  {loading ? <Spinner/> : '获取验证码'}
                </button>

                <div className="flex items-center gap-3 py-1">
                  <div className="h-px flex-1 bg-gray-200" />
                  <span className="text-xs text-gray-400">或</span>
                  <div className="h-px flex-1 bg-gray-200" />
                </div>

                <button onClick={handleGitHubLogin} disabled={!githubEnabled || loading}
                  className="w-full py-3.5 border border-gray-200 bg-white text-gray-800 font-semibold
                             rounded-2xl hover:bg-gray-50 disabled:opacity-40 transition-colors text-sm
                             flex items-center justify-center gap-2">
                  <IconGithub />
                  <span>{loading ? '登录中...' : '使用 GitHub 登录'}</span>
                </button>

                {!githubEnabled && (
                  <p className="text-center text-xs text-amber-500">
                    未配置 VITE_GITHUB_CLIENT_ID，GitHub 登录按钮当前不可用
                  </p>
                )}

                <p className="text-center text-xs text-gray-400 pt-1">
                  登录即代表同意{' '}
                  <a href="#" className="text-indigo-500 hover:underline">用户协议</a>
                  {' '}与{' '}
                  <a href="#" className="text-indigo-500 hover:underline">隐私政策</a>
                </p>
              </div>
            )}

            {/* Step 2: 验证码 */}
            {step === STEP.CODE && (
              <div className="space-y-4">
                <div className="relative">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400">
                    <IconShield />
                  </div>
                  <input type="text" inputMode="numeric" maxLength={6}
                    placeholder="输入 6 位验证码"
                    value={code}
                    onChange={(e) => { setCode(e.target.value.replace(/\D/g, '')); setError('') }}
                    onKeyDown={(e) => e.key === 'Enter' && handleVerifyCode()}
                    className="w-full rounded-2xl border border-gray-200 bg-gray-50 pl-11 pr-4
                               py-3.5 text-sm outline-none focus:border-indigo-400 focus:ring-2
                               focus:ring-indigo-100 transition-all tracking-[0.3em] font-mono"
                    autoFocus/>
                </div>

                {error && <ErrorTip msg={error}/>}

                <button onClick={handleVerifyCode} disabled={code.length !== 6 || loading}
                  className="w-full py-3.5 bg-indigo-600 text-white font-semibold rounded-2xl
                             hover:bg-indigo-700 disabled:opacity-40 transition-colors text-sm">
                  {loading ? <Spinner/> : '验证并登录'}
                </button>

                <div className="text-center">
                  {countdown.running ? (
                    <span className="text-sm text-gray-400">{countdown.count}s 后可重新发送</span>
                  ) : (
                    <button onClick={handleSendCode} disabled={loading}
                      className="text-sm text-indigo-500 hover:text-indigo-700 transition-colors">
                      重新发送验证码
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* 步骤指示器 */}
          <div className="flex justify-center gap-1.5 mt-6">
            {Object.values(STEP).map((s) => (
              <div key={s}
                className={`h-1 rounded-full transition-all duration-300
                  ${s === step ? 'w-6 bg-indigo-500' : 'w-1.5 bg-gray-300'}`}/>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function ErrorTip({ msg }) {
  return (
    <div className="flex items-center gap-2 bg-red-50 border border-red-100 rounded-xl px-3.5 py-2.5">
      <svg className="w-4 h-4 text-red-400 shrink-0" fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd"
          d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1
             0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd"/>
      </svg>
      <span className="text-sm text-red-600">{msg}</span>
    </div>
  )
}

function Spinner() {
  return (
    <svg className="animate-spin h-5 w-5 text-white mx-auto" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
    </svg>
  )
}
