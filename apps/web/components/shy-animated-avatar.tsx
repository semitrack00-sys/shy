'use client';
import React, { useEffect, useRef } from 'react';
import { avatarPose } from '@/lib/avatar-motion';
import type { AvatarState } from './shy-avatar';

/** Original character rendered locally; no remote models, camera or avatar API. */
export function ShyAnimatedAvatar({state,motion,wave,onUnavailable}: {
  state: AvatarState; motion: boolean; wave: number; onUnavailable:()=>void;
}) {
  const host=useRef<HTMLDivElement>(null);
  const current=useRef({state,motion,wave}); current.current={state,motion,wave};
  const failure=useRef(onUnavailable); failure.current=onUnavailable;
  useEffect(()=>{
    let disposed=false, clean=()=>{};
    void import('three').then(T=>{
      if(disposed||!host.current)return;
      if(!window.WebGL2RenderingContext){failure.current();return;}
      const el=host.current;
      let renderer: InstanceType<typeof T.WebGLRenderer>;
      try {renderer=new T.WebGLRenderer({alpha:true,antialias:true,powerPreference:'low-power'});}
      catch {failure.current();return;}
      const scene=new T.Scene(), camera=new T.PerspectiveCamera(34,1,0.1,30);
      camera.position.set(0,1.05,7.3);camera.lookAt(0,1.05,0);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.5));renderer.setClearColor(0,0);el.appendChild(renderer.domElement);
      const sphere=new T.SphereGeometry(1,24,16);
      const materials: InstanceType<typeof T.Material>[]=[];
      const mat=(color:number)=>{const m=new T.MeshStandardMaterial({color,roughness:0.75});materials.push(m);return m;};
      const skin=mat(0x965d3e),lip=mat(0x653d33),hair=mat(0x171820),shirt=mat(0x1c3452),cuff=mat(0x345477),white=mat(0xfff4e4),iris=mat(0x41291e),black=mat(0x141218),shine=mat(0xffffff);
      const ball=(parent: InstanceType<typeof T.Group>, material: InstanceType<typeof T.Material>, x:number,y:number,z:number,sx:number,sy:number,sz:number)=>{
        const mesh=new T.Mesh(sphere,material);mesh.position.set(x,y,z);mesh.scale.set(sx,sy,sz);parent.add(mesh);return mesh;
      };
      scene.add(new T.HemisphereLight(0xdceaff,0x6e4435,2.5));
      const key=new T.DirectionalLight(0xffead6,3);key.position.set(-3,5,5);scene.add(key);
      const rim=new T.DirectionalLight(0x8ab9ff,2);rim.position.set(3,2,-2);scene.add(rim);
      const body=new T.Group();scene.add(body);
      ball(body,shirt,0,0.15,0,0.8,0.82,0.35);ball(body,cuff,0,0.66,0.03,0.35,0.12,0.3);ball(body,skin,0,0.87,0,0.23,0.34,0.23);
      const head=new T.Group();head.position.y=1.15;body.add(head);
      ball(head,skin,0,0.44,0,0.57,0.72,0.47);ball(head,skin,0,0.05,0.13,0.41,0.33,0.36);
      for(const side of [-1,1]) {ball(head,skin,side*0.57,0.4,0,0.105,0.17,0.09);ball(head,lip,side*0.59,0.4,0.06,0.04,0.1,0.025);}
      ball(head,hair,0,0.96,-0.045,0.56,0.29,0.44);
      for(let row=0;row<5;row++)for(let col=0;col<13;col++){
        const a=col/13*Math.PI*2,b=(row+0.5)/5*Math.PI/2,r=0.075+((row*13+col)%3)*0.009;
        ball(head,hair,0.52*Math.sin(b)*Math.cos(a),0.94+0.3*Math.cos(b),-0.035+0.41*Math.sin(b)*Math.sin(a),r,r,r);
      }
      const eyes: InstanceType<typeof T.Group>[]=[];
      for(const side of [-1,1]){
        const eye=new T.Group();eye.position.set(side*0.225,0.5,0.427);head.add(eye);eyes.push(eye);
        ball(eye,white,0,0,0,0.137,0.082,0.047);ball(eye,iris,-side*0.012,0,0.043,0.055,0.059,0.019);ball(eye,black,-side*0.012,0,0.059,0.025,0.032,0.009);ball(eye,shine,-side*0.012-0.014,0.024,0.068,0.012,0.014,0.005);
        const brow=ball(head,hair,side*0.225,0.65,0.42,0.148,0.027,0.035);brow.rotation.z=side*-0.08;
      }
      ball(head,skin,0,0.35,0.47,0.095,0.15,0.12);ball(head,skin,0,0.27,0.54,0.13,0.07,0.075);
      const mouth=new T.Group();mouth.position.set(0,0.105,0.474);head.add(mouth);
      ball(mouth,lip,0,0,0,0.205,0.075,0.035);
      const opening=ball(mouth,black,0,0,0.028,0.17,0.05,0.02),teeth=ball(mouth,white,0,0.018,0.043,0.14,0.018,0.012);
      const arms: InstanceType<typeof T.Group>[]=[];
      for(const side of [-1,1]){
        const arm=new T.Group();arm.position.set(side*0.62,0.62,0);body.add(arm);arms.push(arm);
        ball(arm,shirt,side*0.14,-0.28,0,0.22,0.43,0.25);ball(arm,cuff,side*0.19,-0.55,0.03,0.185,0.09,0.21);ball(arm,skin,side*0.2,-0.73,0.06,0.145,0.26,0.16);
        const hand=new T.Group();hand.position.set(side*0.2,-0.98,0.08);arm.add(hand);ball(hand,skin,0,0,0,0.145,0.18,0.075);
        for(let f=0;f<4;f++)ball(hand,skin,(f-1.5)*0.065,-0.17,0,0.036,0.12-Math.abs(f-1.5)*0.015,0.04);
        ball(hand,skin,-side*0.14,-0.01,0.02,0.055,0.11,0.055).rotation.z=-side*0.5;
      }
      const media=window.matchMedia('(prefers-reduced-motion: reduce)');
      let visible=true,last=0,waveAt=-Infinity,seenWave=current.current.wave,staticDrawn=false;
      const start=performance.now();
      const frame=(now:number)=>{
        if(disposed||document.hidden||!visible||now-last<1000/30)return;
        last=now;const time=(now-start)/1000,enabled=current.current.motion&&!media.matches;
        if(current.current.wave!==seenWave){seenWave=current.current.wave;waveAt=time;}
        if(!enabled&&staticDrawn)return;staticDrawn=!enabled;
        const p=avatarPose(time,current.current.state,enabled,time-waveAt);
        head.rotation.set(p.nod,p.turn,p.tilt);body.position.y=p.breath;eyes.forEach(e=>e.scale.y=p.blink);
        opening.scale.y=0.02+p.mouth*0.11;teeth.position.y=0.018+p.mouth*0.025;
        arms[0].rotation.z=-p.left;arms[1].rotation.z=p.right+p.wave*(2.25+Math.sin(time*12)*0.16);
        arms[0].rotation.x=-p.left*1.4;arms[1].rotation.x=-p.right*1.4;renderer.render(scene,camera);
      };
      const resize=()=>{const w=el.clientWidth,h=el.clientHeight;if(!w||!h)return;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();staticDrawn=false;};
      const observer=new ResizeObserver(resize);observer.observe(el);resize();
      const intersection=new IntersectionObserver(entries=>{visible=entries[0]?.isIntersecting??true;});intersection.observe(el);
      const lost=(event:Event)=>{event.preventDefault();failure.current();};renderer.domElement.addEventListener('webglcontextlost',lost);
      renderer.setAnimationLoop(frame);
      clean=()=>{renderer.setAnimationLoop(null);observer.disconnect();intersection.disconnect();renderer.domElement.removeEventListener('webglcontextlost',lost);sphere.dispose();materials.forEach(m=>m.dispose());renderer.dispose();renderer.forceContextLoss();renderer.domElement.remove();};
    }).catch(()=>{if(!disposed)failure.current();});
    return()=>{disposed=true;clean();};
  },[]);
  return <div className="shy-animated-avatar" ref={host} role="img" aria-label="SHY, an animated 3D AI character"/>;
}
