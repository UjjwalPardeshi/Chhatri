/**
 * Which basemap the live map is showing (SPEC §20 "Live map": CARTO tiles with attribution, or the
 * ward-built fallback). The footer credits CARTO / OpenStreetMap only while real tiles are shown.
 * A tiny external store read with useSyncExternalStore; the map is its only writer.
 */
import { useSyncExternalStore } from 'react'

import type { TileProbe } from '../lib/tiles'

export type BasemapState = 'unknown' | 'tiles' | Exclude<TileProbe, 'ok'> | 'errors'

type Listener = () => void

export class BasemapStore {
  private state: BasemapState = 'unknown'
  private readonly listeners = new Set<Listener>()

  get = (): BasemapState => this.state

  set(next: BasemapState): void {
    if (next === this.state) return
    this.state = next
    for (const listener of this.listeners) listener()
  }

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }
}

export const basemap = new BasemapStore()

export function useBasemap(store: BasemapStore = basemap): BasemapState {
  return useSyncExternalStore(store.subscribe, store.get, store.get)
}
