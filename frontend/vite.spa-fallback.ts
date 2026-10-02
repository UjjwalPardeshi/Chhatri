/**
 * Deep-link fallback for the static build (card 7.1, N7). A static host such as GitHub Pages answers an unknown path
 * (/merchant/S-0142/app) with 404.html, so the build also writes a copy of index.html under that name; the router then
 * reads the address and opens the right page. Hosts with rewrite rules need nothing more (frontend/README.md, Static build).
 */
import type { Plugin } from 'vite'

export function spaFallback(): Plugin {
  return {
    name: 'chhatri-spa-fallback',
    enforce: 'post',
    generateBundle: {
      order: 'post',
      handler(_options, bundle) {
        const index = bundle['index.html']
        if (!index || index.type !== 'asset') throw new Error('spa-fallback: index.html is not in the bundle, so 404.html cannot be written')
        this.emitFile({ type: 'asset', fileName: '404.html', source: index.source })
      },
    },
  }
}
