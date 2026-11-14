import * as THREE from 'three';
import { GLTFLoader } from '/assets/vendor/GLTFLoader.js';

const host=document.getElementById('character-model');
const fallback=document.getElementById('character-fallback');
const motionPreference=window.matchMedia('(prefers-reduced-motion: reduce)');
let paused=motionPreference.matches||document.body.classList.contains('motion-paused');
let currentStep=1,mixer,renderer,scene,camera,clock,actions,resizeObserver;
const clipByStep={1:'Talk',2:'SlipAngry',3:'ReadyDetermined',4:'Done'};
function pose(name){const next=actions?.get(name)||actions?.get('Idle');if(!next)return;if(next!==pose.active){if(pose.active)pose.active.stop();next.reset().setEffectiveWeight(1).play();mixer.update(1/60);next.paused=paused;pose.active=next;if(renderer&&scene&&camera)renderer.render(scene,camera);}}
function stepPose(step){currentStep=step;pose(clipByStep[step]||'Idle');}
window.addEventListener('paoween-step',e=>stepPose(e.detail));
window.addEventListener('paoween-motion',e=>{paused=e.detail||motionPreference.matches;if(pose.active)pose.active.paused=paused;});
motionPreference.addEventListener('change',e=>{paused=e.matches||document.body.classList.contains('motion-paused');if(pose.active)pose.active.paused=paused;});
try{
 scene=new THREE.Scene();renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,powerPreference:'low-power'});renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));renderer.setClearColor(0,0);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.35;renderer.domElement.setAttribute('aria-hidden','true');host.append(renderer.domElement);
 renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();renderer.domElement.hidden=true;fallback.hidden=false;});
 camera=new THREE.OrthographicCamera(-2,2,2,-2,.1,30);camera.position.set(3,1.9,10);camera.lookAt(0,0,0);
 scene.add(new THREE.HemisphereLight(0xfff7e4,0x768b68,2.5));const key=new THREE.DirectionalLight(0xffe9cb,3);key.position.set(-3,5,6);scene.add(key);const fill=new THREE.DirectionalLight(0xffffff,1.3);fill.position.set(4,2,-1);scene.add(fill);
 const gltf=await new GLTFLoader().loadAsync('/assets/paoween/paoween-onboarding.glb?v=8'),model=gltf.scene,box=new THREE.Box3().setFromObject(model),center=box.getCenter(new THREE.Vector3());model.position.sub(center);scene.add(model);
 mixer=new THREE.AnimationMixer(model);actions=new Map(gltf.animations.map(clip=>[clip.name,mixer.clipAction(clip)]));pose('Idle');fallback.hidden=true;
 function resize(){const w=host.clientWidth,h=host.clientHeight;if(!w||!h)return;renderer.setSize(w,h,false);const half=1.8,aspect=w/h;camera.left=-half*aspect;camera.right=half*aspect;camera.top=half;camera.bottom=-half;camera.updateProjectionMatrix();renderer.render(scene,camera);}
 resizeObserver=new ResizeObserver(resize);resizeObserver.observe(host);resize();clock=new THREE.Clock();function frame(){requestAnimationFrame(frame);const delta=Math.min(clock.getDelta(),.05);if(document.hidden)return;if(!paused)mixer.update(delta);renderer.render(scene,camera)}frame();stepPose(currentStep);
}catch(error){if(renderer)renderer.domElement.hidden=true;fallback.hidden=false;console.warn('3D character unavailable; showing still image.',error)}
