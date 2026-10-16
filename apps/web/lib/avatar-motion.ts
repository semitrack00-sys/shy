/** Procedural motion, not phoneme lip-sync. All time values use seconds. */
export function avatarPose(t: number, state: string, enabled: boolean, waveAge = Infinity) {
  if (!enabled) return { blink: 1, mouth: 0.08, nod: 0, turn: 0, tilt: 0, breath: 0, left: 0, right: 0, wave: 0 };
  const speaking=state==='speaking', listening=state==='listening', thinking=state==='thinking'||state==='transcribing';
  const phase=t%4.7;
  return {
    blink: phase>4.45 ? Math.max(0.06,Math.abs((phase-4.575)/0.125)) : 1,
    mouth: speaking ? 0.12+0.65*Math.abs(Math.sin(t*9.3)*Math.cos(t*3.8)) : 0.08,
    nod: speaking ? Math.sin(t*2.6)*0.045 : listening ? Math.sin(t*1.9)*0.035 : 0,
    turn: Math.sin(t*0.65)*(thinking?0.12:0.045),
    tilt: thinking?-0.08:listening?0.055:Math.sin(t*0.9)*0.025,
    breath: Math.sin(t*1.6)*0.014,
    left: speaking?0.18+Math.sin(t*2.1)*0.13:0,
    right: speaking?0.22+Math.sin(t*1.7+1)*0.13:0,
    wave: waveAge>=0&&waveAge<2.4 ? Math.min(1,waveAge/0.3,(2.4-waveAge)/0.3) : 0,
  };
}
