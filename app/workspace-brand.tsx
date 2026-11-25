import Image from "next/image";

export function Brand({ priority = false }: { priority?: boolean }) {
  return <Image
    className="workspace-logo"
    src="/garje-marathi-logo.png"
    alt="Garje Marathi Global"
    width={445}
    height={220}
    priority={priority}
  />;
}

const mission = [
  { title: "Connect", marathi: "जोडणी", detail: "Bring Marathi people together across borders." },
  { title: "Mentor", marathi: "मार्गदर्शन", detail: "Share experiences with students, professionals, and entrepreneurs." },
  { title: "Give back", marathi: "योगदान", detail: "Put that knowledge to work for our communities." },
];

export function MissionArt() {
  return <aside className="auth-art" aria-labelledby="mission-heading">
    <div className="mission-content">
      <h2 id="mission-heading">Rooted in Maharashtra.<br /><em>Connected across the world.</em></h2>
      <div className="mission-map">
        <div className="mission-root" aria-hidden="true"><span lang="mr">ग</span><small lang="mr">महाराष्ट्र</small></div>
        <ol className="mission-steps">
          {mission.map((step, index) => <li className={`mission-step step-${index + 1}`} key={step.title}>
            <span className="mission-branch" aria-hidden="true"><i /></span>
            <div className="mission-node">
              <strong>{step.title} <span lang="mr">{step.marathi}</span></strong>
              <p>{step.detail}</p>
            </div>
          </li>)}
        </ol>
      </div>
    </div>
  </aside>;
}
