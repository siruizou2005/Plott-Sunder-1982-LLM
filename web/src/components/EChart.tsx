import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, ScatterChart } from 'echarts/charts'
import {
  DataZoomComponent, GridComponent, LegendComponent, MarkAreaComponent,
  MarkLineComponent, TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useStore } from '../store'

echarts.use([
  LineChart, ScatterChart, BarChart, GridComponent, TooltipComponent, MarkLineComponent,
  MarkAreaComponent, LegendComponent, DataZoomComponent, CanvasRenderer,
])

/** Thin wrapper: init on mount, resize with the container, dispose on unmount. */
export function EChart({ option, height = 280 }: { option: any; height?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const chart = useRef<echarts.ECharts | null>(null)
  const lang = useStore((s) => s.lang)

  useEffect(() => {
    if (!ref.current) return
    chart.current = echarts.init(ref.current)

    // Resizing has to be deferred and de-duplicated, not run straight from the observer.
    // Redrawing the canvas can change the page height, which toggles the scrollbar, which
    // changes the container width, which fires the observer again — a feedback loop that
    // locks the whole tab. Rounding to whole pixels drops the no-op notifications and the
    // rAF makes the remaining ones asynchronous, so the cycle cannot close.
    let raf = 0
    let last = { w: 0, h: 0 }
    const ro = new ResizeObserver((entries) => {
      const r = entries[0]?.contentRect
      if (!r) return
      const w = Math.round(r.width), h = Math.round(r.height)
      if (w === last.w && h === last.h) return
      last = { w, h }
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => chart.current?.resize())
    })
    ro.observe(ref.current)
    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      chart.current?.dispose()
      chart.current = null
    }
  }, [])

  useEffect(() => {
    chart.current?.setOption(option, true)
  }, [option, lang])

  return <div ref={ref} style={{ height }} className="w-full" />
}

/** Shared axis/tooltip styling so every chart in the app reads as one system. */
export const axisStyle = {
  axisLine: { lineStyle: { color: '#cbd5e1' } },
  axisLabel: { color: '#64748b', fontSize: 11 },
  splitLine: { lineStyle: { color: 'rgba(148,163,184,0.18)' } },
}

export const tooltipStyle = {
  trigger: 'axis' as const,
  backgroundColor: 'rgba(15,23,42,0.92)',
  borderWidth: 0,
  textStyle: { color: '#e2e8f0', fontSize: 11 },
}
