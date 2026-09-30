import { Icon } from '../common/Icon'

/** Chhatri wordmark (deck slide 1: "Chhatri · छतरी · umbrella"). */
export function Brand() {
  return (
    <>
      <span className="brand__mark">
        <Icon name="umbrella" size={20} />
      </span>
      <span className="brand__word">Chhatri</span>
      <span className="brand__hi hi" lang="hi">
        छतरी
      </span>
    </>
  )
}
