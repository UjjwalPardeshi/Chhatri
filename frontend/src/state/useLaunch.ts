/**
 * Scenario jumps for the Overview and Policy pages (SPEC §17.1 load/seek/play, §19 /api/replay/*
 * and the phone endpoints): load a scenario, seek to the story moment, run any scripted phone
 * steps, open the page that shows it, then optionally play so the moment happens live on screen.
 * Failures stay visible inline, next to the button that asked for the jump.
 */
import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router'

import type { ApiError } from '../api/client'
import type { Api } from '../api/endpoints'
import type { Launch, LaunchAction } from '../content/deck'
import { useLive } from './live'
import { toApiError } from './useAsync'

export type LaunchState = {
  busy: string | null
  /** The last failed jump, shown next to the button that asked for it. */
  failure: { key: string; error: ApiError } | null
  errorFor: (keys: readonly string[]) => ApiError | null
  launch: (key: string, target: Launch) => Promise<void>
}

/** Navigation state a launched page can read (e.g. the phone highlights the `hint` chip). */
export type LaunchNavState = { hint: string }

function runAction(api: Api, action: LaunchAction): Promise<unknown> {
  return action.kind === 'voice' ? api.sendVoiceDemo(action.merchant, action.key) : api.sendSampleSlip(action.merchant, action.file)
}

export function useLaunch(): LaunchState {
  const { api, refresh, replay, pauseAt } = useLive()
  const navigate = useNavigate()
  const [busy, setBusy] = useState<string | null>(null)
  const [failure, setFailure] = useState<{ key: string; error: ApiError } | null>(null)
  const launch = useCallback(
    async (key: string, target: Launch) => {
      setBusy(key)
      setFailure(null)
      try {
        await api.load(target.scenario)
        if (target.seek) await api.seek(target.seek)
        for (const action of target.actions ?? []) await runAction(api, action)
        refresh()
        const state: LaunchNavState | undefined = target.hint ? { hint: target.hint } : undefined
        navigate(target.to, { state })
        /** Playing goes through the shared replay control, so a failure shows in the control bar. */
        if (target.play !== undefined) await replay('play', target.play)
        if (target.play !== undefined && target.pauseAt) pauseAt({ scenario: target.scenario, at: target.pauseAt })
      } catch (reason) {
        const error = toApiError(reason)
        console.warn('[launch] scenario jump failed', error.code)
        setFailure({ key, error })
      } finally {
        setBusy(null)
      }
    },
    [api, navigate, pauseAt, refresh, replay],
  )
  const errorFor = useCallback((keys: readonly string[]) => (failure && keys.includes(failure.key) ? failure.error : null), [failure])
  return { busy, failure, errorFor, launch }
}
