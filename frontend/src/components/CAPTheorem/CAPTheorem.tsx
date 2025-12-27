import './CAPTheorem.css'

export function CAPTheorem() {
  return (
    <div className="cap-theorem-panel">
      <div className="cap-header">
        <h2>CAP Theorem</h2>
        <span className="cap-badge">MongoDB: CP</span>
      </div>

      <div className="cap-content">
        <div className="cap-explanation">
          <p>
            Distributed systems can only guarantee two out of three properties:
          </p>
          <ul className="cap-properties">
            <li className="cap-property selected">
              <span className="property-icon">C</span>
              <div>
                <strong>Consistency</strong>
                <p>All nodes see the same data at the same time</p>
              </div>
            </li>
            <li className="cap-property selected">
              <span className="property-icon">P</span>
              <div>
                <strong>Partition Tolerance</strong>
                <p>System continues to operate despite network partitions</p>
              </div>
            </li>
            <li className="cap-property">
              <span className="property-icon">A</span>
              <div>
                <strong>Availability</strong>
                <p>Every request receives a response</p>
              </div>
            </li>
          </ul>
        </div>d
      </div>
    </div>
  )
}
