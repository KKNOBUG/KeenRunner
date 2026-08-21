import{d as Y,B as $,f as w,a5 as j,ak as U,aA as M,h as p,aB as v,aC as Q,c as _,aD as ee,aE as x,a as ae,aF as te,az as ne,aG as le,aH as se,aI as D,u as oe,b as J,aJ as ie,X as re,e as de,H as ue,g as ce,aK as fe,aL as me,aM as pe,aN as be,_ as ve,ac as he,ad as ye,V as ge,o as E,k as A,w as b,q as V,F as xe,v as _e,m as u,n as o,y as we,a7 as Se,l as N,O as $e,a6 as F,t as Oe,z as k,$ as Ne,aq as Ce,x as Ee}from"./index-6352ab0f.js";import{g as Be}from"./Empty-7bd5d2d8.js";import{_ as P}from"./TheIcon-e494ce78.js";import{w as Re,A as K,x as ze,y as Ae,P as Te,z as ke,i as L,g as Pe,k as Ie,B as W,s as X,C as Me}from"./useStepEditorForm-ab2e2f99.js";import{_ as T}from"./Select-b78cb528.js";import{_ as q}from"./Space-33304a0a.js";import{_ as Ye,a as C}from"./FormItem-bc1e76ea.js";import{_ as I}from"./Input-6aba4075.js";const H=Y({name:"SlotMachineNumber",props:{clsPrefix:{type:String,required:!0},value:{type:[Number,String],required:!0},oldOriginalNumber:{type:Number,default:void 0},newOriginalNumber:{type:Number,default:void 0}},setup(e){const l=$(null),t=$(e.value),m=$(e.value),s=$("up"),a=$(!1),y=w(()=>a.value?`${e.clsPrefix}-base-slot-machine-current-number--${s.value}-scroll`:null),S=w(()=>a.value?`${e.clsPrefix}-base-slot-machine-old-number--${s.value}-scroll`:null);j(M(e,"value"),(i,h)=>{t.value=h,m.value=i,U(R)});function R(){const i=e.newOriginalNumber,h=e.oldOriginalNumber;h===void 0||i===void 0||(i>h?O("up"):h>i&&O("down"))}function O(i){s.value=i,a.value=!1,U(()=>{var h;(h=l.value)===null||h===void 0||h.offsetWidth,a.value=!0})}return()=>{const{clsPrefix:i}=e;return p("span",{ref:l,class:`${i}-base-slot-machine-number`},t.value!==null?p("span",{class:[`${i}-base-slot-machine-old-number ${i}-base-slot-machine-old-number--top`,S.value]},t.value):null,p("span",{class:[`${i}-base-slot-machine-current-number`,y.value]},p("span",{ref:"numberWrapper",class:[`${i}-base-slot-machine-current-number__inner`,typeof e.value!="number"&&`${i}-base-slot-machine-current-number__inner--not-number`]},m.value)),t.value!==null?p("span",{class:[`${i}-base-slot-machine-old-number ${i}-base-slot-machine-old-number--bottom`,S.value]},t.value):null)}}}),{cubicBezierEaseOut:B}=Q;function je({duration:e=".2s"}={}){return[v("&.fade-up-width-expand-transition-leave-active",{transition:`
 opacity ${e} ${B},
 max-width ${e} ${B},
 transform ${e} ${B}
 `}),v("&.fade-up-width-expand-transition-enter-active",{transition:`
 opacity ${e} ${B},
 max-width ${e} ${B},
 transform ${e} ${B}
 `}),v("&.fade-up-width-expand-transition-enter-to",{opacity:1,transform:"translateX(0) translateY(0)"}),v("&.fade-up-width-expand-transition-enter-from",{maxWidth:"0 !important",opacity:0,transform:"translateY(60%)"}),v("&.fade-up-width-expand-transition-leave-from",{opacity:1,transform:"translateY(0)"}),v("&.fade-up-width-expand-transition-leave-to",{maxWidth:"0 !important",opacity:0,transform:"translateY(60%)"})]}const Ue=v([v("@keyframes n-base-slot-machine-fade-up-in",`
 from {
 transform: translateY(60%);
 opacity: 0;
 }
 to {
 transform: translateY(0);
 opacity: 1;
 }
 `),v("@keyframes n-base-slot-machine-fade-down-in",`
 from {
 transform: translateY(-60%);
 opacity: 0;
 }
 to {
 transform: translateY(0);
 opacity: 1;
 }
 `),v("@keyframes n-base-slot-machine-fade-up-out",`
 from {
 transform: translateY(0%);
 opacity: 1;
 }
 to {
 transform: translateY(-60%);
 opacity: 0;
 }
 `),v("@keyframes n-base-slot-machine-fade-down-out",`
 from {
 transform: translateY(0%);
 opacity: 1;
 }
 to {
 transform: translateY(60%);
 opacity: 0;
 }
 `),_("base-slot-machine",`
 overflow: hidden;
 white-space: nowrap;
 display: inline-block;
 height: 18px;
 line-height: 18px;
 `,[_("base-slot-machine-number",`
 display: inline-block;
 position: relative;
 height: 18px;
 width: .6em;
 max-width: .6em;
 `,[je({duration:".2s"}),ee({duration:".2s",delay:"0s"}),_("base-slot-machine-old-number",`
 display: inline-block;
 opacity: 0;
 position: absolute;
 left: 0;
 right: 0;
 `,[x("top",{transform:"translateY(-100%)"}),x("bottom",{transform:"translateY(100%)"}),x("down-scroll",{animation:"n-base-slot-machine-fade-down-out .2s cubic-bezier(0, 0, .2, 1)",animationIterationCount:1}),x("up-scroll",{animation:"n-base-slot-machine-fade-up-out .2s cubic-bezier(0, 0, .2, 1)",animationIterationCount:1})]),_("base-slot-machine-current-number",`
 display: inline-block;
 position: absolute;
 left: 0;
 top: 0;
 bottom: 0;
 right: 0;
 opacity: 1;
 transform: translateY(0);
 width: .6em;
 `,[x("down-scroll",{animation:"n-base-slot-machine-fade-down-in .2s cubic-bezier(0, 0, .2, 1)",animationIterationCount:1}),x("up-scroll",{animation:"n-base-slot-machine-fade-up-in .2s cubic-bezier(0, 0, .2, 1)",animationIterationCount:1}),ae("inner",`
 display: inline-block;
 position: absolute;
 right: 0;
 top: 0;
 width: .6em;
 `,[x("not-number",`
 right: unset;
 left: 0;
 `)])])])])]),De=Y({name:"BaseSlotMachine",props:{clsPrefix:{type:String,required:!0},value:{type:[Number,String],default:0},max:{type:Number,default:void 0},appeared:{type:Boolean,required:!0}},setup(e){te("-base-slot-machine",Ue,M(e,"clsPrefix"));const l=$(),t=$(),m=w(()=>{if(typeof e.value=="string")return[];if(e.value<1)return[0];const s=[];let a=e.value;for(e.max!==void 0&&(a=Math.min(e.max,a));a>=1;)s.push(a%10),a/=10,a=Math.floor(a);return s.reverse(),s});return j(M(e,"value"),(s,a)=>{typeof s=="string"?(t.value=void 0,l.value=void 0):typeof a=="string"?(t.value=s,l.value=void 0):(t.value=s,l.value=a)}),()=>{const{value:s,clsPrefix:a}=e;return typeof s=="number"?p("span",{class:`${a}-base-slot-machine`},p(le,{name:"fade-up-width-expand-transition",tag:"span"},{default:()=>m.value.map((y,S)=>p(H,{clsPrefix:a,key:m.value.length-S-1,oldOriginalNumber:l.value,newOriginalNumber:t.value,value:y}))}),p(ne,{key:"+",width:!0},{default:()=>e.max!==void 0&&e.max<s?p(H,{clsPrefix:a,value:"+"}):null})):p("span",{class:`${a}-base-slot-machine`},s)}}});function Ve(e){const{errorColor:l,infoColor:t,successColor:m,warningColor:s,fontFamily:a}=e;return{color:l,colorInfo:t,colorSuccess:m,colorError:l,colorWarning:s,fontSize:"12px",fontFamily:a}}const Fe={name:"Badge",common:se,self:Ve},Ke=Fe,Le=v([v("@keyframes badge-wave-spread",{from:{boxShadow:"0 0 0.5px 0px var(--n-ripple-color)",opacity:.6},to:{boxShadow:"0 0 0.5px 4.5px var(--n-ripple-color)",opacity:0}}),_("badge",`
 display: inline-flex;
 position: relative;
 vertical-align: middle;
 font-family: var(--n-font-family);
 `,[x("as-is",[_("badge-sup",{position:"static",transform:"translateX(0)"},[D({transformOrigin:"left bottom",originalTransform:"translateX(0)"})])]),x("dot",[_("badge-sup",`
 height: 8px;
 width: 8px;
 padding: 0;
 min-width: 8px;
 left: 100%;
 bottom: calc(100% - 4px);
 `,[v("::before","border-radius: 4px;")])]),_("badge-sup",`
 background: var(--n-color);
 transition:
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 color: #FFF;
 position: absolute;
 height: 18px;
 line-height: 18px;
 border-radius: 9px;
 padding: 0 6px;
 text-align: center;
 font-size: var(--n-font-size);
 transform: translateX(-50%);
 left: 100%;
 bottom: calc(100% - 9px);
 font-variant-numeric: tabular-nums;
 z-index: 1;
 display: flex;
 align-items: center;
 `,[D({transformOrigin:"left bottom",originalTransform:"translateX(-50%)"}),_("base-wave",{zIndex:1,animationDuration:"2s",animationIterationCount:"infinite",animationDelay:"1s",animationTimingFunction:"var(--n-ripple-bezier)",animationName:"badge-wave-spread"}),v("&::before",`
 opacity: 0;
 transform: scale(1);
 border-radius: 9px;
 content: "";
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 `)])])]),We=Object.assign(Object.assign({},J.props),{value:[String,Number],max:Number,dot:Boolean,type:{type:String,default:"default"},show:{type:Boolean,default:!0},showZero:Boolean,processing:Boolean,color:String,offset:Array}),ra=Y({name:"Badge",props:We,setup(e,{slots:l}){const{mergedClsPrefixRef:t,inlineThemeDisabled:m,mergedRtlRef:s}=oe(e),a=J("Badge","-badge",Le,Ke,e,t),y=$(!1),S=()=>{y.value=!0},R=()=>{y.value=!1},O=w(()=>e.show&&(e.dot||e.value!==void 0&&!(!e.showZero&&Number(e.value)<=0)||!ie(l.value)));re(()=>{O.value&&(y.value=!0)});const i=de("Badge",s,t),h=w(()=>{const{type:r,color:n}=e,{common:{cubicBezierEaseInOut:f,cubicBezierEaseOut:d},self:{[ue("color",r)]:z,fontFamily:G,fontSize:Z}}=a.value;return{"--n-font-size":Z,"--n-font-family":G,"--n-color":n||z,"--n-ripple-color":n||z,"--n-bezier":f,"--n-ripple-bezier":d}}),g=m?ce("badge",w(()=>{let r="";const{type:n,color:f}=e;return n&&(r+=n[0]),f&&(r+=fe(f)),r}),h,e):void 0,c=w(()=>{const{offset:r}=e;if(!r)return;const[n,f]=r,d=typeof n=="number"?`${n}px`:n,z=typeof f=="number"?`${f}px`:f;return{transform:`translate(calc(${i?.value?"50%":"-50%"} + ${d}), ${z})`}});return{rtlEnabled:i,mergedClsPrefix:t,appeared:y,showBadge:O,handleAfterEnter:S,handleAfterLeave:R,cssVars:m?void 0:h,themeClass:g?.themeClass,onRender:g?.onRender,offsetStyle:c}},render(){var e;const{mergedClsPrefix:l,onRender:t,themeClass:m,$slots:s}=this;t?.();const a=(e=s.default)===null||e===void 0?void 0:e.call(s);return p("div",{class:[`${l}-badge`,this.rtlEnabled&&`${l}-badge--rtl`,m,{[`${l}-badge--dot`]:this.dot,[`${l}-badge--as-is`]:!a}],style:this.cssVars},a,p(me,{name:"fade-in-scale-up-transition",onAfterEnter:this.handleAfterEnter,onAfterLeave:this.handleAfterLeave},{default:()=>this.showBadge?p("sup",{class:`${l}-badge-sup`,title:Be(this.value),style:this.offsetStyle},pe(s.value,()=>[this.dot?null:p(De,{clsPrefix:l,appeared:this.appeared,max:this.max,value:this.value})]),this.processing?p(be,{clsPrefix:l}):null):null}))}});const Xe={class:"extract-validator-card-header"},qe=["onClick","onKeydown"],He={class:"extract-validator-title"},Je={class:"step-ev-rows"},Ge={class:"step-ev-row step-ev-row--assert"},Ze={class:"step-ev-row step-ev-row--assert"},Qe={__name:"StepAssertPanel",props:he({mode:{type:String,default:L,validator:e=>[L,Pe,Ie,K].includes(e)},readonly:{type:Boolean,default:!1},sourceOptions:{type:Array,default:()=>[]},defaultObject:{type:String,default:null},lockObject:{type:Boolean,default:!1}},{modelValue:{type:Object,default:()=>({})},modelModifiers:{}}),emits:["update:modelValue"],setup(e){const l=e,t=ye(e,"modelValue"),m=w(()=>Re(l.mode)),s=w(()=>l.mode===K),a=ge({});function y(){const c=new Set(Object.keys(t.value||{}));Object.keys(a).forEach(r=>{c.has(r)||delete a[r]}),c.forEach(r=>{a[r]===void 0&&(a[r]=!0)})}j(t,y,{deep:!0,immediate:!0});function S(){return m.value?l.sourceOptions[0]?.value??null:null}function R(c){return m.value?W(null,l.mode):W(c?.object,l.mode)}function O(){const c=X(t.value);t.value[c]=Me(l.mode,S(),l.defaultObject),a[c]=!1}function i(c){delete t.value[c],delete a[c]}function h(c){const r=t.value[c];if(!r)return;const n=X(t.value);t.value[n]={...JSON.parse(JSON.stringify(r)),name:r.name?`${r.name}_副本`:""},a[n]=a[c]??!0}function g(c){a[c]=!a[c]}return(c,r)=>(E(),A(o(q),{vertical:"",size:8,class:"extract-validator-list"},{default:b(()=>[(E(!0),V(xe,null,_e(t.value,(n,f)=>(E(),V("div",{key:f,class:"validator-item"},[u(o(we),{size:"small",hoverable:"",class:Se({"is-item-collapsed":a[f]})},{header:b(()=>[N("div",Xe,[N("div",{class:"extract-validator-title-wrap",role:"button",tabindex:"0",onClick:d=>g(f),onKeydown:$e(F(d=>g(f),["prevent"]),["enter"])},[u(P,{class:"extract-validator-collapse-icon",icon:a[f]?"material-symbols:chevron-right":"material-symbols:expand-more",size:20},null,8,["icon"]),N("span",He,Oe(o(ze)(n,e.mode)),1)],40,qe),u(o(q),{onClick:r[0]||(r[0]=F(()=>{},["stop"]))},{default:b(()=>[u(o(k),{text:"",type:"info",size:"small",disabled:e.readonly,onClick:d=>h(f)},{icon:b(()=>[u(P,{icon:"material-symbols:content-copy",size:18})]),_:2},1032,["disabled","onClick"]),u(o(k),{text:"",type:"error",size:"small",disabled:e.readonly,onClick:d=>i(f)},{icon:b(()=>[u(P,{icon:"material-symbols:delete-outline",size:18})]),_:2},1032,["disabled","onClick"])]),_:2},1024)])]),default:b(()=>[Ne(N("div",null,[u(o(Ye),{model:n,"label-width":"90px","label-placement":"left",size:"small",class:"step-ev-form"},{default:b(()=>[N("div",Je,[N("div",Ge,[u(o(C),{label:"断言名称",class:"step-ev-fi step-ev-fi--span2"},{default:b(()=>[u(o(I),{value:n.name,"onUpdate:value":d=>n.name=d,placeholder:"请输入断言名称",clearable:"",disabled:e.readonly},null,8,["value","onUpdate:value","disabled"])]),_:2},1024),m.value?(E(),A(o(C),{key:0,label:"断言对象",class:"step-ev-fi"},{default:b(()=>[u(o(T),{value:n.source,"onUpdate:value":d=>n.source=d,options:e.sourceOptions,placeholder:"选择「请求」中的存储变量名（variable_name）",filterable:"",clearable:"",disabled:e.readonly||!e.sourceOptions.length},null,8,["value","onUpdate:value","options","disabled"])]),_:2},1024)):s.value?(E(),A(o(C),{key:2,label:"断言对象",class:"step-ev-fi"},{default:b(()=>[u(o(T),{value:n.object,"onUpdate:value":d=>n.object=d,options:o(Te),placeholder:"变量池",disabled:e.readonly||e.lockObject},null,8,["value","onUpdate:value","options","disabled"])]),_:2},1024)):(E(),A(o(C),{key:1,label:"断言对象",class:"step-ev-fi"},{default:b(()=>[u(o(T),{value:n.object,"onUpdate:value":d=>n.object=d,options:o(Ae),placeholder:"请选择断言对象",disabled:e.readonly},null,8,["value","onUpdate:value","options","disabled"])]),_:2},1024))]),N("div",Ze,[u(o(C),{label:"断言表达式",class:"step-ev-fi"},{default:b(()=>[u(o(I),{value:n.jsonpath,"onUpdate:value":d=>n.jsonpath=d,placeholder:R(n),clearable:"",disabled:e.readonly},null,8,["value","onUpdate:value","placeholder","disabled"])]),_:2},1024),u(o(C),{label:"断言操作符",class:"step-ev-fi"},{default:b(()=>[u(o(T),{value:n.assertion,"onUpdate:value":d=>n.assertion=d,options:o(ke),placeholder:"请选择断言方法",disabled:e.readonly},null,8,["value","onUpdate:value","options","disabled"])]),_:2},1024),u(o(C),{label:"断言预期值",class:"step-ev-fi"},{default:b(()=>[u(o(I),{value:n.value,"onUpdate:value":d=>n.value=d,placeholder:"请输入预期值",clearable:"",disabled:e.readonly},null,8,["value","onUpdate:value","disabled"])]),_:2},1024)])])]),_:2},1032,["model"])],512),[[Ce,!a[f]]])]),_:2},1032,["class"])]))),128)),u(o(k),{type:"primary",block:"",dashed:"",disabled:e.readonly,onClick:O},{default:b(()=>[Ee("添加断言")]),_:1},8,["disabled"])]),_:1}))}},da=ve(Qe,[["__scopeId","data-v-4da101c3"]]);export{ra as N,da as S};
