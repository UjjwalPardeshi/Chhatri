import {
  CircleCheckIcon,
  InfoIcon,
  Loader2Icon,
  OctagonXIcon,
  TriangleAlertIcon,
} from "lucide-react"
import { Toaster as Sonner, type ToasterProps } from "sonner"

/** Light only, and the colours are console tokens (the shadcn names --popover and --border do not exist here). */
const Toaster = ({ ...props }: ToasterProps) => (
  <Sonner
    theme="light"
    className="toaster group"
    icons={{
      success: <CircleCheckIcon className="size-4" />,
      info: <InfoIcon className="size-4" />,
      warning: <TriangleAlertIcon className="size-4" />,
      error: <OctagonXIcon className="size-4" />,
      loading: <Loader2Icon className="size-4 animate-spin" />,
    }}
    style={
      {
        "--normal-bg": "var(--card)",
        "--normal-text": "var(--ink)",
        "--normal-border": "var(--line)",
        "--border-radius": "var(--radius-card)",
      } as React.CSSProperties
    }
    {...props}
  />
)

export { Toaster }
