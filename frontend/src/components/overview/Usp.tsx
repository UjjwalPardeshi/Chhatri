/**
 * What Chhatri adds (deck slide 10): the comparison with a traditional merchant claim and
 * weather-only cover, the Chhatri column tinted as the answer, and the deck's closing line.
 * Stacks into one card per row on a phone.
 */
import { USP } from '../../content/deckValue'
import { RevealSection } from './Reveal'

const OURS = USP.columns.length - 1

export function Usp() {
  return (
    <RevealSection label="What Chhatri adds" className="ov-usp" tone="white">
      <h2 className="ov-h2">{USP.title}</h2>
      <table className="usp">
        <thead>
          <tr>
            <th scope="col">
              <span className="visually-hidden">Question</span>
            </th>
            {USP.columns.map((column, i) => (
              <th key={column} scope="col" className={i === OURS ? 'usp__ours' : undefined}>
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {USP.rows.map((row) => (
            <tr key={row.label}>
              <th scope="row">{row.label}</th>
              {row.cells.map((cell, i) => (
                <td key={USP.columns[i]} className={i === OURS ? 'usp__ours' : undefined} data-label={USP.columns[i]}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="usp__caption">{USP.caption}</p>
      <p className="ov-source">{USP.sources}</p>
    </RevealSection>
  )
}
