/** Smoke tests for the mini-app scope (ADR 0005): shadcn parts render inside `.miniapp`, portals stay inside it. */
import { render, screen } from '@testing-library/react'
import type { ReactElement } from 'react'
import { describe, expect, it } from 'vitest'

import { MiniappRoot } from './MiniappRoot'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from './ui/accordion'
import { Alert, AlertTitle } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from './ui/dialog'
import { Input } from './ui/input'
import { Label } from './ui/label'
import { Progress } from './ui/progress'
import { ScrollArea } from './ui/scroll-area'
import { Separator } from './ui/separator'
import { Sheet, SheetContent, SheetDescription, SheetTitle } from './ui/sheet'
import { Skeleton } from './ui/skeleton'
import { Switch } from './ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs'
import { Textarea } from './ui/textarea'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip'

const IN_FLOW: ReadonlyArray<readonly [slot: string, element: ReactElement]> = [
  ['button', <Button key="button">Pay</Button>],
  [
    'card',
    <Card key="card">
      <CardHeader>
        <CardTitle>Cover</CardTitle>
      </CardHeader>
      <CardContent>Active</CardContent>
    </Card>,
  ],
  ['badge', <Badge key="badge">SIMULATED</Badge>],
  [
    'tabs',
    <Tabs key="tabs" defaultValue="cover">
      <TabsList>
        <TabsTrigger value="cover">Cover</TabsTrigger>
      </TabsList>
      <TabsContent value="cover">Cover details</TabsContent>
    </Tabs>,
  ],
  [
    'accordion',
    <Accordion key="accordion" type="single" collapsible>
      <AccordionItem value="what">
        <AccordionTrigger>What is covered</AccordionTrigger>
        <AccordionContent>A rain day.</AccordionContent>
      </AccordionItem>
    </Accordion>,
  ],
  ['progress', <Progress key="progress" value={40} aria-label="Claim progress" />],
  ['skeleton', <Skeleton key="skeleton" className="h-4 w-24" />],
  ['switch', <Switch key="switch" aria-label="Share sales data" />],
  ['input', <Input key="input" aria-label="Amount" />],
  ['textarea', <Textarea key="textarea" aria-label="Note" />],
  ['label', <Label key="label">Phone</Label>],
  ['alert', <Alert key="alert"><AlertTitle>Offline</AlertTitle></Alert>],
  ['separator', <Separator key="separator" />],
  [
    'scroll-area',
    <ScrollArea key="scroll-area" className="h-10">
      <p>Receipt</p>
    </ScrollArea>,
  ],
]

describe('MiniappRoot', () => {
  it('renders a shadcn component inside .miniapp with its Tailwind classes', () => {
    const { container } = render(
      <MiniappRoot>
        <Button>Pay</Button>
      </MiniappRoot>,
    )
    const root = container.querySelector('.miniapp')
    const button = screen.getByRole('button', { name: 'Pay' })
    expect(root?.contains(button)).toBe(true)
    expect(button.dataset.slot).toBe('button')
    expect(button.classList.contains('inline-flex')).toBe(true)
    expect(button.classList.contains('bg-primary')).toBe(true)
    expect(root?.classList.contains('h-full')).toBe(true) // the clip, stacking context and container come from the scoped base
  })

  it.each(IN_FLOW)('renders the %s component inside the .miniapp scope', (slot, element) => {
    const { container } = render(<MiniappRoot>{element}</MiniappRoot>)
    expect(container.querySelector(`.miniapp [data-slot="${slot}"]`)).not.toBeNull()
  })
})

function OpenDialog() {
  return (
    <Dialog open>
      <DialogContent>
        <DialogTitle>Receipt</DialogTitle>
        <DialogDescription>How the amount was worked out</DialogDescription>
      </DialogContent>
    </Dialog>
  )
}

describe('portals', () => {
  it('mounts a Dialog inside the .miniapp scope where the theme names resolve', () => {
    const { container } = render(
      <MiniappRoot>
        <OpenDialog />
      </MiniappRoot>,
    )
    expect(container.querySelector('.miniapp')?.contains(screen.getByRole('dialog'))).toBe(true)
  })

  it('mounts a Sheet inside the .miniapp scope', () => {
    const { container } = render(
      <MiniappRoot>
        <Sheet open>
          <SheetContent side="bottom">
            <SheetTitle>Jargon</SheetTitle>
            <SheetDescription>What this word means</SheetDescription>
          </SheetContent>
        </Sheet>
      </MiniappRoot>,
    )
    const sheet = screen.getByRole('dialog')
    expect(container.querySelector('.miniapp')?.contains(sheet)).toBe(true)
    expect(sheet.classList.contains('bottom-0')).toBe(true)
  })

  it('mounts a Tooltip inside the .miniapp scope', () => {
    const { container } = render(
      <MiniappRoot>
        <TooltipProvider>
          <Tooltip open>
            <TooltipTrigger asChild>
              <button type="button">Why</button>
            </TooltipTrigger>
            <TooltipContent>Formula</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </MiniappRoot>,
    )
    expect(container.querySelector('.miniapp')?.contains(screen.getByRole('tooltip'))).toBe(true)
  })

  it('without the root, Radix falls back to document.body (outside the scope)', () => {
    const { container } = render(<OpenDialog />)
    expect(container.contains(screen.getByRole('dialog'))).toBe(false)
    expect(document.body.contains(screen.getByRole('dialog'))).toBe(true)
  })
})
