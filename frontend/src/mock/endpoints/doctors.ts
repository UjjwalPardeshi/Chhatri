/**
 * The officer's doctor enrolment routes in the mock (design 2.9, flag telegram_channel): one item per directory doctor.
 * The static demo has no bot, so no link is known (`deep_link` null), no chat is ever enrolled and the simulated doctor
 * answers. A reset is audited as on the backend, with the registration number only (never a link or a token).
 */
import type { DoctorEnrolment } from '../../api/types'
import { isFeatureEnabled } from '../../features'
import { DIRECTORY_DOCTORS, type DirectoryDoctor } from '../doctor'
import { notFound, ok, requireOfficer, type Handler, type Route } from '../http'

function gate(): void {
  if (!isFeatureEnabled('telegram_channel')) throw notFound('route')
}

const item = (doctor: DirectoryDoctor): DoctorEnrolment => ({
  registration_no: doctor.registration_no,
  doctor_name: doctor.name,
  hospital_id: doctor.hospital_id,
  hospital_name: doctor.hospital_name,
  enrolled: false,
  deep_link: null,
  answers: 'SIMULATED',
})

const links: Handler = (ctx) => {
  gate()
  requireOfficer(ctx)
  return ok(DIRECTORY_DOCTORS.map(item))
}

const reset: Handler = (ctx) => {
  gate()
  requireOfficer(ctx)
  const doctor = DIRECTORY_DOCTORS.find((d) => d.registration_no === decodeURIComponent(ctx.params[0]))
  if (!doctor) throw notFound(`doctor ${ctx.params[0]}`)
  ctx.backend.runtime.record('officer:officer', 'doctor.enrolment_reset', 'doctor', doctor.registration_no, { registration_no: doctor.registration_no })
  return ok(item(doctor))
}

export const DOCTOR_ROUTES: readonly Route[] = [
  { method: 'POST', pattern: /^\/api\/doctors\/enrolment-links$/, handler: links },
  { method: 'POST', pattern: /^\/api\/doctors\/([A-Za-z0-9%-]+)\/enrolment-link\/reset$/, handler: reset },
]
