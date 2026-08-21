import{d as Q,bu as me,B as E,bv as pt,bw as vt,h as c,bx as ht,by as J,bz as gt,aX as mt,ae as ze,aY as xt,f as K,A as yt,F as wt,N as St,bA as Ct,aS as Rt,bB as Tt,c as r,aE as i,aB as S,a as L,bc as zt,u as $t,b as $e,bC as xe,bs as ae,b5 as Pt,a5 as re,X as Wt,ao as _t,aA as k,bD as At,a$ as Et,H as j,aR as Y,g as Lt,r as ye,bE as ne,bF as Bt,b8 as q,br as kt,ak as oe,$ as jt,aq as It,aG as Ht,bG as Ot}from"./index-6352ab0f.js";import{A as Ft}from"./Add-362a65a9.js";const Dt=me(".v-x-scroll",{overflow:"auto",scrollbarWidth:"none"},[me("&::-webkit-scrollbar",{width:0,height:0})]),Mt=Q({name:"XScroll",props:{disabled:Boolean,onScroll:Function},setup(){const e=E(null);function n(l){!(l.currentTarget.offsetWidth<l.currentTarget.scrollWidth)||l.deltaY===0||(l.currentTarget.scrollLeft+=l.deltaY+l.deltaX,l.preventDefault())}const d=pt();return Dt.mount({id:"vueuc/x-scroll",head:!0,anchorMetaName:vt,ssr:d}),Object.assign({selfRef:e,handleWheel:n},{scrollTo(...l){var x;(x=e.value)===null||x===void 0||x.scrollTo(...l)}})},render(){return c("div",{ref:"selfRef",onScroll:this.onScroll,onWheel:this.disabled?void 0:this.handleWheel,class:"v-x-scroll"},this.$slots)}});var Nt=/\s/;function Vt(e){for(var n=e.length;n--&&Nt.test(e.charAt(n)););return n}var Xt=/^\s+/;function Ut(e){return e&&e.slice(0,Vt(e)+1).replace(Xt,"")}var we=0/0,Gt=/^[-+]0x[0-9a-f]+$/i,Yt=/^0b[01]+$/i,qt=/^0o[0-7]+$/i,Kt=parseInt;function Se(e){if(typeof e=="number")return e;if(ht(e))return we;if(J(e)){var n=typeof e.valueOf=="function"?e.valueOf():e;e=J(n)?n+"":n}if(typeof e!="string")return e===0?e:+e;e=Ut(e);var d=Yt.test(e);return d||qt.test(e)?Kt(e.slice(2),d?2:8):Gt.test(e)?we:+e}var Jt=function(){return gt.Date.now()};const ie=Jt;var Qt="Expected a function",Zt=Math.max,ea=Math.min;function ta(e,n,d){var p,l,x,v,f,m,h=0,g=!1,W=!1,_=!0;if(typeof e!="function")throw new TypeError(Qt);n=Se(n)||0,J(d)&&(g=!!d.leading,W="maxWait"in d,x=W?Zt(Se(d.maxWait)||0,n):x,_="trailing"in d?!!d.trailing:_);function y(b){var R=p,F=l;return p=l=void 0,h=b,v=e.apply(F,R),v}function T(b){return h=b,f=setTimeout(P,n),g?y(b):v}function C(b){var R=b-m,F=b-h,N=n-R;return W?ea(N,x-F):N}function $(b){var R=b-m,F=b-h;return m===void 0||R>=n||R<0||W&&F>=x}function P(){var b=ie();if($(b))return z(b);f=setTimeout(P,C(b))}function z(b){return f=void 0,_&&p?y(b):(p=l=void 0,v)}function O(){f!==void 0&&clearTimeout(f),h=0,p=m=l=f=void 0}function A(){return f===void 0?v:z(ie())}function u(){var b=ie(),R=$(b);if(p=arguments,l=this,m=b,R){if(f===void 0)return T(m);if(W)return clearTimeout(f),f=setTimeout(P,n),y(m)}return f===void 0&&(f=setTimeout(P,n)),v}return u.cancel=O,u.flush=A,u}var aa="Expected a function";function se(e,n,d){var p=!0,l=!0;if(typeof e!="function")throw new TypeError(aa);return J(d)&&(p="leading"in d?!!d.leading:p,l="trailing"in d?!!d.trailing:l),ta(e,n,{leading:p,maxWait:n,trailing:l})}const ce=mt("n-tabs"),Pe={tab:[String,Number,Object,Function],name:{type:[String,Number],required:!0},disabled:Boolean,displayDirective:{type:String,default:"if"},closable:{type:Boolean,default:void 0},tabProps:Object,label:[String,Number,Object,Function]},la=Q({__TAB_PANE__:!0,name:"TabPane",alias:["TabPanel"],props:Pe,setup(e){const n=ze(ce,null);return n||xt("tab-pane","`n-tab-pane` must be placed inside `n-tabs`."),{style:n.paneStyleRef,class:n.paneClassRef,mergedClsPrefix:n.mergedClsPrefixRef}},render(){return c("div",{class:[`${this.mergedClsPrefix}-tab-pane`,this.class],style:this.style},this.$slots)}}),ra=Object.assign({internalLeftPadded:Boolean,internalAddable:Boolean,internalCreatedByPane:Boolean},Tt(Pe,["displayDirective"])),de=Q({__TAB__:!0,inheritAttrs:!1,name:"Tab",props:ra,setup(e){const{mergedClsPrefixRef:n,valueRef:d,typeRef:p,closableRef:l,tabStyleRef:x,addTabStyleRef:v,tabClassRef:f,addTabClassRef:m,tabChangeIdRef:h,onBeforeLeaveRef:g,triggerRef:W,handleAdd:_,activateTab:y,handleClose:T}=ze(ce);return{trigger:W,mergedClosable:K(()=>{if(e.internalAddable)return!1;const{closable:C}=e;return C===void 0?l.value:C}),style:x,addStyle:v,tabClass:f,addTabClass:m,clsPrefix:n,value:d,type:p,handleClose(C){C.stopPropagation(),!e.disabled&&T(e.name)},activateTab(){if(e.disabled)return;if(e.internalAddable){_();return}const{name:C}=e,$=++h.id;if(C!==d.value){const{value:P}=g;P?Promise.resolve(P(e.name,d.value)).then(z=>{z&&h.id===$&&y(C)}):y(C)}}}},render(){const{internalAddable:e,clsPrefix:n,name:d,disabled:p,label:l,tab:x,value:v,mergedClosable:f,trigger:m,$slots:{default:h}}=this,g=l??x;return c("div",{class:`${n}-tabs-tab-wrapper`},this.internalLeftPadded?c("div",{class:`${n}-tabs-tab-pad`}):null,c("div",Object.assign({key:d,"data-name":d,"data-disabled":p?!0:void 0},yt({class:[`${n}-tabs-tab`,v===d&&`${n}-tabs-tab--active`,p&&`${n}-tabs-tab--disabled`,f&&`${n}-tabs-tab--closable`,e&&`${n}-tabs-tab--addable`,e?this.addTabClass:this.tabClass],onClick:m==="click"?this.activateTab:void 0,onMouseenter:m==="hover"?this.activateTab:void 0,style:e?this.addStyle:this.style},this.internalCreatedByPane?this.tabProps||{}:this.$attrs)),c("span",{class:`${n}-tabs-tab__label`},e?c(wt,null,c("div",{class:`${n}-tabs-tab__height-placeholder`}," "),c(St,{clsPrefix:n},{default:()=>c(Ft,null)})):h?h():typeof g=="object"?g:Ct(g??d)),f&&this.type==="card"?c(Rt,{clsPrefix:n,class:`${n}-tabs-tab__close`,onClick:this.handleClose,disabled:p}):null))}}),na=r("tabs",`
 box-sizing: border-box;
 width: 100%;
 display: flex;
 flex-direction: column;
 transition:
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
`,[i("segment-type",[r("tabs-rail",[S("&.transition-disabled",[r("tabs-capsule",`
 transition: none;
 `)])])]),i("top",[r("tab-pane",`
 padding: var(--n-pane-padding-top) var(--n-pane-padding-right) var(--n-pane-padding-bottom) var(--n-pane-padding-left);
 `)]),i("left",[r("tab-pane",`
 padding: var(--n-pane-padding-right) var(--n-pane-padding-bottom) var(--n-pane-padding-left) var(--n-pane-padding-top);
 `)]),i("left, right",`
 flex-direction: row;
 `,[r("tabs-bar",`
 width: 2px;
 right: 0;
 transition:
 top .2s var(--n-bezier),
 max-height .2s var(--n-bezier),
 background-color .3s var(--n-bezier);
 `),r("tabs-tab",`
 padding: var(--n-tab-padding-vertical); 
 `)]),i("right",`
 flex-direction: row-reverse;
 `,[r("tab-pane",`
 padding: var(--n-pane-padding-left) var(--n-pane-padding-top) var(--n-pane-padding-right) var(--n-pane-padding-bottom);
 `),r("tabs-bar",`
 left: 0;
 `)]),i("bottom",`
 flex-direction: column-reverse;
 justify-content: flex-end;
 `,[r("tab-pane",`
 padding: var(--n-pane-padding-bottom) var(--n-pane-padding-right) var(--n-pane-padding-top) var(--n-pane-padding-left);
 `),r("tabs-bar",`
 top: 0;
 `)]),r("tabs-rail",`
 position: relative;
 padding: 3px;
 border-radius: var(--n-tab-border-radius);
 width: 100%;
 background-color: var(--n-color-segment);
 transition: background-color .3s var(--n-bezier);
 display: flex;
 align-items: center;
 `,[r("tabs-capsule",`
 border-radius: var(--n-tab-border-radius);
 position: absolute;
 pointer-events: none;
 background-color: var(--n-tab-color-segment);
 box-shadow: 0 1px 3px 0 rgba(0, 0, 0, .08);
 transition: transform 0.3s var(--n-bezier);
 `),r("tabs-tab-wrapper",`
 flex-basis: 0;
 flex-grow: 1;
 display: flex;
 align-items: center;
 justify-content: center;
 `,[r("tabs-tab",`
 overflow: hidden;
 border-radius: var(--n-tab-border-radius);
 width: 100%;
 display: flex;
 align-items: center;
 justify-content: center;
 `,[i("active",`
 font-weight: var(--n-font-weight-strong);
 color: var(--n-tab-text-color-active);
 `),S("&:hover",`
 color: var(--n-tab-text-color-hover);
 `)])])]),i("flex",[r("tabs-nav",`
 width: 100%;
 position: relative;
 `,[r("tabs-wrapper",`
 width: 100%;
 `,[r("tabs-tab",`
 margin-right: 0;
 `)])])]),r("tabs-nav",`
 box-sizing: border-box;
 line-height: 1.5;
 display: flex;
 transition: border-color .3s var(--n-bezier);
 `,[L("prefix, suffix",`
 display: flex;
 align-items: center;
 `),L("prefix","padding-right: 16px;"),L("suffix","padding-left: 16px;")]),i("top, bottom",[r("tabs-nav-scroll-wrapper",[S("&::before",`
 top: 0;
 bottom: 0;
 left: 0;
 width: 20px;
 `),S("&::after",`
 top: 0;
 bottom: 0;
 right: 0;
 width: 20px;
 `),i("shadow-start",[S("&::before",`
 box-shadow: inset 10px 0 8px -8px rgba(0, 0, 0, .12);
 `)]),i("shadow-end",[S("&::after",`
 box-shadow: inset -10px 0 8px -8px rgba(0, 0, 0, .12);
 `)])])]),i("left, right",[r("tabs-nav-scroll-content",`
 flex-direction: column;
 `),r("tabs-nav-scroll-wrapper",[S("&::before",`
 top: 0;
 left: 0;
 right: 0;
 height: 20px;
 `),S("&::after",`
 bottom: 0;
 left: 0;
 right: 0;
 height: 20px;
 `),i("shadow-start",[S("&::before",`
 box-shadow: inset 0 10px 8px -8px rgba(0, 0, 0, .12);
 `)]),i("shadow-end",[S("&::after",`
 box-shadow: inset 0 -10px 8px -8px rgba(0, 0, 0, .12);
 `)])])]),r("tabs-nav-scroll-wrapper",`
 flex: 1;
 position: relative;
 overflow: hidden;
 `,[r("tabs-nav-y-scroll",`
 height: 100%;
 width: 100%;
 overflow-y: auto; 
 scrollbar-width: none;
 `,[S("&::-webkit-scrollbar",`
 width: 0;
 height: 0;
 `)]),S("&::before, &::after",`
 transition: box-shadow .3s var(--n-bezier);
 pointer-events: none;
 content: "";
 position: absolute;
 z-index: 1;
 `)]),r("tabs-nav-scroll-content",`
 display: flex;
 position: relative;
 min-width: 100%;
 min-height: 100%;
 width: fit-content;
 box-sizing: border-box;
 `),r("tabs-wrapper",`
 display: inline-flex;
 flex-wrap: nowrap;
 position: relative;
 `),r("tabs-tab-wrapper",`
 display: flex;
 flex-wrap: nowrap;
 flex-shrink: 0;
 flex-grow: 0;
 `),r("tabs-tab",`
 cursor: pointer;
 white-space: nowrap;
 flex-wrap: nowrap;
 display: inline-flex;
 align-items: center;
 color: var(--n-tab-text-color);
 font-size: var(--n-tab-font-size);
 background-clip: padding-box;
 padding: var(--n-tab-padding);
 transition:
 box-shadow .3s var(--n-bezier),
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `,[i("disabled",{cursor:"not-allowed"}),L("close",`
 margin-left: 6px;
 transition:
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 `),L("label",`
 display: flex;
 align-items: center;
 z-index: 1;
 `)]),r("tabs-bar",`
 position: absolute;
 bottom: 0;
 height: 2px;
 border-radius: 1px;
 background-color: var(--n-bar-color);
 transition:
 left .2s var(--n-bezier),
 max-width .2s var(--n-bezier),
 opacity .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 `,[S("&.transition-disabled",`
 transition: none;
 `),i("disabled",`
 background-color: var(--n-tab-text-color-disabled)
 `)]),r("tabs-pane-wrapper",`
 position: relative;
 overflow: hidden;
 transition: max-height .2s var(--n-bezier);
 `),r("tab-pane",`
 color: var(--n-pane-text-color);
 width: 100%;
 transition:
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 opacity .2s var(--n-bezier);
 left: 0;
 right: 0;
 top: 0;
 `,[S("&.next-transition-leave-active, &.prev-transition-leave-active, &.next-transition-enter-active, &.prev-transition-enter-active",`
 transition:
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 transform .2s var(--n-bezier),
 opacity .2s var(--n-bezier);
 `),S("&.next-transition-leave-active, &.prev-transition-leave-active",`
 position: absolute;
 `),S("&.next-transition-enter-from, &.prev-transition-leave-to",`
 transform: translateX(32px);
 opacity: 0;
 `),S("&.next-transition-leave-to, &.prev-transition-enter-from",`
 transform: translateX(-32px);
 opacity: 0;
 `),S("&.next-transition-leave-from, &.next-transition-enter-to, &.prev-transition-leave-from, &.prev-transition-enter-to",`
 transform: translateX(0);
 opacity: 1;
 `)]),r("tabs-tab-pad",`
 box-sizing: border-box;
 width: var(--n-tab-gap);
 flex-grow: 0;
 flex-shrink: 0;
 `),i("line-type, bar-type",[r("tabs-tab",`
 font-weight: var(--n-tab-font-weight);
 box-sizing: border-box;
 vertical-align: bottom;
 `,[S("&:hover",{color:"var(--n-tab-text-color-hover)"}),i("active",`
 color: var(--n-tab-text-color-active);
 font-weight: var(--n-tab-font-weight-active);
 `),i("disabled",{color:"var(--n-tab-text-color-disabled)"})])]),r("tabs-nav",[i("line-type",[i("top",[L("prefix, suffix",`
 border-bottom: 1px solid var(--n-tab-border-color);
 `),r("tabs-nav-scroll-content",`
 border-bottom: 1px solid var(--n-tab-border-color);
 `),r("tabs-bar",`
 bottom: -1px;
 `)]),i("left",[L("prefix, suffix",`
 border-right: 1px solid var(--n-tab-border-color);
 `),r("tabs-nav-scroll-content",`
 border-right: 1px solid var(--n-tab-border-color);
 `),r("tabs-bar",`
 right: -1px;
 `)]),i("right",[L("prefix, suffix",`
 border-left: 1px solid var(--n-tab-border-color);
 `),r("tabs-nav-scroll-content",`
 border-left: 1px solid var(--n-tab-border-color);
 `),r("tabs-bar",`
 left: -1px;
 `)]),i("bottom",[L("prefix, suffix",`
 border-top: 1px solid var(--n-tab-border-color);
 `),r("tabs-nav-scroll-content",`
 border-top: 1px solid var(--n-tab-border-color);
 `),r("tabs-bar",`
 top: -1px;
 `)]),L("prefix, suffix",`
 transition: border-color .3s var(--n-bezier);
 `),r("tabs-nav-scroll-content",`
 transition: border-color .3s var(--n-bezier);
 `),r("tabs-bar",`
 border-radius: 0;
 `)]),i("card-type",[L("prefix, suffix",`
 transition: border-color .3s var(--n-bezier);
 border-bottom: 1px solid var(--n-tab-border-color);
 `),r("tabs-pad",`
 flex-grow: 1;
 transition: border-color .3s var(--n-bezier);
 `),r("tabs-tab-pad",`
 transition: border-color .3s var(--n-bezier);
 `),r("tabs-tab",`
 font-weight: var(--n-tab-font-weight);
 border: 1px solid var(--n-tab-border-color);
 background-color: var(--n-tab-color);
 box-sizing: border-box;
 position: relative;
 vertical-align: bottom;
 display: flex;
 justify-content: space-between;
 font-size: var(--n-tab-font-size);
 color: var(--n-tab-text-color);
 `,[i("addable",`
 padding-left: 8px;
 padding-right: 8px;
 font-size: 16px;
 `,[L("height-placeholder",`
 width: 0;
 font-size: var(--n-tab-font-size);
 `),zt("disabled",[S("&:hover",`
 color: var(--n-tab-text-color-hover);
 `)])]),i("closable","padding-right: 8px;"),i("active",`
 background-color: #0000;
 font-weight: var(--n-tab-font-weight-active);
 color: var(--n-tab-text-color-active);
 `),i("disabled","color: var(--n-tab-text-color-disabled);")]),r("tabs-scroll-padding","border-bottom: 1px solid var(--n-tab-border-color);")]),i("left, right",[r("tabs-wrapper",`
 flex-direction: column;
 `,[r("tabs-tab-wrapper",`
 flex-direction: column;
 `,[r("tabs-tab-pad",`
 height: var(--n-tab-gap-vertical);
 width: 100%;
 `)])])]),i("top",[i("card-type",[r("tabs-tab",`
 border-top-left-radius: var(--n-tab-border-radius);
 border-top-right-radius: var(--n-tab-border-radius);
 `,[i("active",`
 border-bottom: 1px solid #0000;
 `)]),r("tabs-tab-pad",`
 border-bottom: 1px solid var(--n-tab-border-color);
 `),r("tabs-pad",`
 border-bottom: 1px solid var(--n-tab-border-color);
 `)])]),i("left",[i("card-type",[r("tabs-tab",`
 border-top-left-radius: var(--n-tab-border-radius);
 border-bottom-left-radius: var(--n-tab-border-radius);
 `,[i("active",`
 border-right: 1px solid #0000;
 `)]),r("tabs-tab-pad",`
 border-right: 1px solid var(--n-tab-border-color);
 `),r("tabs-pad",`
 border-right: 1px solid var(--n-tab-border-color);
 `)])]),i("right",[i("card-type",[r("tabs-tab",`
 border-top-right-radius: var(--n-tab-border-radius);
 border-bottom-right-radius: var(--n-tab-border-radius);
 `,[i("active",`
 border-left: 1px solid #0000;
 `)]),r("tabs-tab-pad",`
 border-left: 1px solid var(--n-tab-border-color);
 `),r("tabs-pad",`
 border-left: 1px solid var(--n-tab-border-color);
 `)])]),i("bottom",[i("card-type",[r("tabs-tab",`
 border-bottom-left-radius: var(--n-tab-border-radius);
 border-bottom-right-radius: var(--n-tab-border-radius);
 `,[i("active",`
 border-top: 1px solid #0000;
 `)]),r("tabs-tab-pad",`
 border-top: 1px solid var(--n-tab-border-color);
 `),r("tabs-pad",`
 border-top: 1px solid var(--n-tab-border-color);
 `)])])])]),oa=Object.assign(Object.assign({},$e.props),{value:[String,Number],defaultValue:[String,Number],trigger:{type:String,default:"click"},type:{type:String,default:"bar"},closable:Boolean,justifyContent:String,size:{type:String,default:"medium"},placement:{type:String,default:"top"},tabStyle:[String,Object],tabClass:String,addTabStyle:[String,Object],addTabClass:String,barWidth:Number,paneClass:String,paneStyle:[String,Object],paneWrapperClass:String,paneWrapperStyle:[String,Object],addable:[Boolean,Object],tabsPadding:{type:Number,default:0},animated:Boolean,onBeforeLeave:Function,onAdd:Function,"onUpdate:value":[Function,Array],onUpdateValue:[Function,Array],onClose:[Function,Array],labelSize:String,activeName:[String,Number],onActiveNameChange:[Function,Array]}),da=Q({name:"Tabs",props:oa,setup(e,{slots:n}){var d,p,l,x;const{mergedClsPrefixRef:v,inlineThemeDisabled:f}=$t(e),m=$e("Tabs","-tabs",na,Bt,e,v),h=E(null),g=E(null),W=E(null),_=E(null),y=E(null),T=E(null),C=E(!0),$=E(!0),P=xe(e,["labelSize","size"]),z=xe(e,["activeName","value"]),O=E((p=(d=z.value)!==null&&d!==void 0?d:e.defaultValue)!==null&&p!==void 0?p:n.default?(x=(l=ae(n.default())[0])===null||l===void 0?void 0:l.props)===null||x===void 0?void 0:x.name:null),A=Pt(z,O),u={id:0},b=K(()=>{if(!(!e.justifyContent||e.type==="card"))return{display:"flex",justifyContent:e.justifyContent}});re(A,()=>{u.id=0,V(),fe()});function R(){var t;const{value:a}=A;return a===null?null:(t=h.value)===null||t===void 0?void 0:t.querySelector(`[data-name="${a}"]`)}function F(t){if(e.type==="card")return;const{value:a}=g;if(!a)return;const o=a.style.opacity==="0";if(t){const s=`${v.value}-tabs-bar--disabled`,{barWidth:w,placement:B}=e;if(t.dataset.disabled==="true"?a.classList.add(s):a.classList.remove(s),["top","bottom"].includes(B)){if(be(["top","maxHeight","height"]),typeof w=="number"&&t.offsetWidth>=w){const H=Math.floor((t.offsetWidth-w)/2)+t.offsetLeft;a.style.left=`${H}px`,a.style.maxWidth=`${w}px`}else a.style.left=`${t.offsetLeft}px`,a.style.maxWidth=`${t.offsetWidth}px`;a.style.width="8192px",o&&(a.style.transition="none"),a.offsetWidth,o&&(a.style.transition="",a.style.opacity="1")}else{if(be(["left","maxWidth","width"]),typeof w=="number"&&t.offsetHeight>=w){const H=Math.floor((t.offsetHeight-w)/2)+t.offsetTop;a.style.top=`${H}px`,a.style.maxHeight=`${w}px`}else a.style.top=`${t.offsetTop}px`,a.style.maxHeight=`${t.offsetHeight}px`;a.style.height="8192px",o&&(a.style.transition="none"),a.offsetHeight,o&&(a.style.transition="",a.style.opacity="1")}}}function N(){if(e.type==="card")return;const{value:t}=g;t&&(t.style.opacity="0")}function be(t){const{value:a}=g;if(a)for(const o of t)a.style[o]=""}function V(){if(e.type==="card")return;const t=R();t?F(t):N()}function fe(){var t;const a=(t=y.value)===null||t===void 0?void 0:t.$el;if(!a)return;const o=R();if(!o)return;const{scrollLeft:s,offsetWidth:w}=a,{offsetLeft:B,offsetWidth:H}=o;s>B?a.scrollTo({top:0,left:B,behavior:"smooth"}):B+H>s+w&&a.scrollTo({top:0,left:B+H-w,behavior:"smooth"})}const X=E(null);let Z=0,I=null;function We(t){const a=X.value;if(a){Z=t.getBoundingClientRect().height;const o=`${Z}px`,s=()=>{a.style.height=o,a.style.maxHeight=o};I?(s(),I(),I=null):I=s}}function _e(t){const a=X.value;if(a){const o=t.getBoundingClientRect().height,s=()=>{document.body.offsetHeight,a.style.maxHeight=`${o}px`,a.style.height=`${Math.max(Z,o)}px`};I?(I(),I=null,s()):I=s}}function Ae(){const t=X.value;if(t){t.style.maxHeight="",t.style.height="";const{paneWrapperStyle:a}=e;if(typeof a=="string")t.style.cssText=a;else if(a){const{maxHeight:o,height:s}=a;o!==void 0&&(t.style.maxHeight=o),s!==void 0&&(t.style.height=s)}}}const ue={value:[]},pe=E("next");function Ee(t){const a=A.value;let o="next";for(const s of ue.value){if(s===a)break;if(s===t){o="prev";break}}pe.value=o,Le(t)}function Le(t){const{onActiveNameChange:a,onUpdateValue:o,"onUpdate:value":s}=e;a&&q(a,t),o&&q(o,t),s&&q(s,t),O.value=t}function Be(t){const{onClose:a}=e;a&&q(a,t)}function ve(){const{value:t}=g;if(!t)return;const a="transition-disabled";t.classList.add(a),V(),t.classList.remove(a)}const D=E(null);function ee({transitionDisabled:t}){const a=h.value;if(!a)return;t&&a.classList.add("transition-disabled");const o=R();o&&D.value&&(D.value.style.width=`${o.offsetWidth}px`,D.value.style.height=`${o.offsetHeight}px`,D.value.style.transform=`translateX(${o.offsetLeft-kt(getComputedStyle(a).paddingLeft)}px)`,t&&D.value.offsetWidth),t&&a.classList.remove("transition-disabled")}re([A],()=>{e.type==="segment"&&oe(()=>{ee({transitionDisabled:!1})})}),Wt(()=>{e.type==="segment"&&ee({transitionDisabled:!0})});let he=0;function ke(t){var a;if(t.contentRect.width===0&&t.contentRect.height===0||he===t.contentRect.width)return;he=t.contentRect.width;const{type:o}=e;if((o==="line"||o==="bar")&&ve(),o!=="segment"){const{placement:s}=e;te((s==="top"||s==="bottom"?(a=y.value)===null||a===void 0?void 0:a.$el:T.value)||null)}}const je=se(ke,64);re([()=>e.justifyContent,()=>e.size],()=>{oe(()=>{const{type:t}=e;(t==="line"||t==="bar")&&ve()})});const U=E(!1);function Ie(t){var a;const{target:o,contentRect:{width:s}}=t,w=o.parentElement.offsetWidth;if(!U.value)w<s&&(U.value=!0);else{const{value:B}=_;if(!B)return;w-s>B.$el.offsetWidth&&(U.value=!1)}te(((a=y.value)===null||a===void 0?void 0:a.$el)||null)}const He=se(Ie,64);function Oe(){const{onAdd:t}=e;t&&t(),oe(()=>{const a=R(),{value:o}=y;!a||!o||o.scrollTo({left:a.offsetLeft,top:0,behavior:"smooth"})})}function te(t){if(!t)return;const{placement:a}=e;if(a==="top"||a==="bottom"){const{scrollLeft:o,scrollWidth:s,offsetWidth:w}=t;C.value=o<=0,$.value=o+w>=s}else{const{scrollTop:o,scrollHeight:s,offsetHeight:w}=t;C.value=o<=0,$.value=o+w>=s}}const Fe=se(t=>{te(t.target)},64);_t(ce,{triggerRef:k(e,"trigger"),tabStyleRef:k(e,"tabStyle"),tabClassRef:k(e,"tabClass"),addTabStyleRef:k(e,"addTabStyle"),addTabClassRef:k(e,"addTabClass"),paneClassRef:k(e,"paneClass"),paneStyleRef:k(e,"paneStyle"),mergedClsPrefixRef:v,typeRef:k(e,"type"),closableRef:k(e,"closable"),valueRef:A,tabChangeIdRef:u,onBeforeLeaveRef:k(e,"onBeforeLeave"),activateTab:Ee,handleClose:Be,handleAdd:Oe}),At(()=>{V(),fe()}),Et(()=>{const{value:t}=W;if(!t)return;const{value:a}=v,o=`${a}-tabs-nav-scroll-wrapper--shadow-start`,s=`${a}-tabs-nav-scroll-wrapper--shadow-end`;C.value?t.classList.remove(o):t.classList.add(o),$.value?t.classList.remove(s):t.classList.add(s)});const De={syncBarPosition:()=>{V()}},Me=()=>{ee({transitionDisabled:!0})},ge=K(()=>{const{value:t}=P,{type:a}=e,o={card:"Card",bar:"Bar",line:"Line",segment:"Segment"}[a],s=`${t}${o}`,{self:{barColor:w,closeIconColor:B,closeIconColorHover:H,closeIconColorPressed:Ne,tabColor:Ve,tabBorderColor:Xe,paneTextColor:Ue,tabFontWeight:Ge,tabBorderRadius:Ye,tabFontWeightActive:qe,colorSegment:Ke,fontWeightStrong:Je,tabColorSegment:Qe,closeSize:Ze,closeIconSize:et,closeColorHover:tt,closeColorPressed:at,closeBorderRadius:rt,[j("panePadding",t)]:G,[j("tabPadding",s)]:nt,[j("tabPaddingVertical",s)]:ot,[j("tabGap",s)]:it,[j("tabGap",`${s}Vertical`)]:st,[j("tabTextColor",a)]:lt,[j("tabTextColorActive",a)]:dt,[j("tabTextColorHover",a)]:ct,[j("tabTextColorDisabled",a)]:bt,[j("tabFontSize",t)]:ft},common:{cubicBezierEaseInOut:ut}}=m.value;return{"--n-bezier":ut,"--n-color-segment":Ke,"--n-bar-color":w,"--n-tab-font-size":ft,"--n-tab-text-color":lt,"--n-tab-text-color-active":dt,"--n-tab-text-color-disabled":bt,"--n-tab-text-color-hover":ct,"--n-pane-text-color":Ue,"--n-tab-border-color":Xe,"--n-tab-border-radius":Ye,"--n-close-size":Ze,"--n-close-icon-size":et,"--n-close-color-hover":tt,"--n-close-color-pressed":at,"--n-close-border-radius":rt,"--n-close-icon-color":B,"--n-close-icon-color-hover":H,"--n-close-icon-color-pressed":Ne,"--n-tab-color":Ve,"--n-tab-font-weight":Ge,"--n-tab-font-weight-active":qe,"--n-tab-padding":nt,"--n-tab-padding-vertical":ot,"--n-tab-gap":it,"--n-tab-gap-vertical":st,"--n-pane-padding-left":Y(G,"left"),"--n-pane-padding-right":Y(G,"right"),"--n-pane-padding-top":Y(G,"top"),"--n-pane-padding-bottom":Y(G,"bottom"),"--n-font-weight-strong":Je,"--n-tab-color-segment":Qe}}),M=f?Lt("tabs",K(()=>`${P.value[0]}${e.type[0]}`),ge,e):void 0;return Object.assign({mergedClsPrefix:v,mergedValue:A,renderedNames:new Set,segmentCapsuleElRef:D,tabsPaneWrapperRef:X,tabsElRef:h,barElRef:g,addTabInstRef:_,xScrollInstRef:y,scrollWrapperElRef:W,addTabFixed:U,tabWrapperStyle:b,handleNavResize:je,mergedSize:P,handleScroll:Fe,handleTabsResize:He,cssVars:f?void 0:ge,themeClass:M?.themeClass,animationDirection:pe,renderNameListRef:ue,yScrollElRef:T,handleSegmentResize:Me,onAnimationBeforeLeave:We,onAnimationEnter:_e,onAnimationAfterEnter:Ae,onRender:M?.onRender},De)},render(){const{mergedClsPrefix:e,type:n,placement:d,addTabFixed:p,addable:l,mergedSize:x,renderNameListRef:v,onRender:f,paneWrapperClass:m,paneWrapperStyle:h,$slots:{default:g,prefix:W,suffix:_}}=this;f?.();const y=g?ae(g()).filter(u=>u.type.__TAB_PANE__===!0):[],T=g?ae(g()).filter(u=>u.type.__TAB__===!0):[],C=!T.length,$=n==="card",P=n==="segment",z=!$&&!P&&this.justifyContent;v.value=[];const O=()=>{const u=c("div",{style:this.tabWrapperStyle,class:[`${e}-tabs-wrapper`]},z?null:c("div",{class:`${e}-tabs-scroll-padding`,style:{width:`${this.tabsPadding}px`}}),C?y.map((b,R)=>(v.value.push(b.props.name),le(c(de,Object.assign({},b.props,{internalCreatedByPane:!0,internalLeftPadded:R!==0&&(!z||z==="center"||z==="start"||z==="end")}),b.children?{default:b.children.tab}:void 0)))):T.map((b,R)=>(v.value.push(b.props.name),le(R!==0&&!z?Te(b):b))),!p&&l&&$?Re(l,(C?y.length:T.length)!==0):null,z?null:c("div",{class:`${e}-tabs-scroll-padding`,style:{width:`${this.tabsPadding}px`}}));return c("div",{ref:"tabsElRef",class:`${e}-tabs-nav-scroll-content`},$&&l?c(ne,{onResize:this.handleTabsResize},{default:()=>u}):u,$?c("div",{class:`${e}-tabs-pad`}):null,$?null:c("div",{ref:"barElRef",class:`${e}-tabs-bar`}))},A=P?"top":d;return c("div",{class:[`${e}-tabs`,this.themeClass,`${e}-tabs--${n}-type`,`${e}-tabs--${x}-size`,z&&`${e}-tabs--flex`,`${e}-tabs--${A}`],style:this.cssVars},c("div",{class:[`${e}-tabs-nav--${n}-type`,`${e}-tabs-nav--${A}`,`${e}-tabs-nav`]},ye(W,u=>u&&c("div",{class:`${e}-tabs-nav__prefix`},u)),P?c(ne,{onResize:this.handleSegmentResize},{default:()=>c("div",{class:`${e}-tabs-rail`,ref:"tabsElRef"},c("div",{class:`${e}-tabs-capsule`,ref:"segmentCapsuleElRef"},c("div",{class:`${e}-tabs-wrapper`},c("div",{class:`${e}-tabs-tab`}))),C?y.map((u,b)=>(v.value.push(u.props.name),c(de,Object.assign({},u.props,{internalCreatedByPane:!0,internalLeftPadded:b!==0}),u.children?{default:u.children.tab}:void 0))):T.map((u,b)=>(v.value.push(u.props.name),b===0?u:Te(u))))}):c(ne,{onResize:this.handleNavResize},{default:()=>c("div",{class:`${e}-tabs-nav-scroll-wrapper`,ref:"scrollWrapperElRef"},["top","bottom"].includes(A)?c(Mt,{ref:"xScrollInstRef",onScroll:this.handleScroll},{default:O}):c("div",{class:`${e}-tabs-nav-y-scroll`,onScroll:this.handleScroll,ref:"yScrollElRef"},O()))}),p&&l&&$?Re(l,!0):null,ye(_,u=>u&&c("div",{class:`${e}-tabs-nav__suffix`},u))),C&&(this.animated&&(A==="top"||A==="bottom")?c("div",{ref:"tabsPaneWrapperRef",style:h,class:[`${e}-tabs-pane-wrapper`,m]},Ce(y,this.mergedValue,this.renderedNames,this.onAnimationBeforeLeave,this.onAnimationEnter,this.onAnimationAfterEnter,this.animationDirection)):Ce(y,this.mergedValue,this.renderedNames)))}});function Ce(e,n,d,p,l,x,v){const f=[];return e.forEach(m=>{const{name:h,displayDirective:g,"display-directive":W}=m.props,_=T=>g===T||W===T,y=n===h;if(m.key!==void 0&&(m.key=h),y||_("show")||_("show:lazy")&&d.has(h)){d.has(h)||d.add(h);const T=!_("if");f.push(T?jt(m,[[It,y]]):m)}}),v?c(Ht,{name:`${v}-transition`,onBeforeLeave:p,onEnter:l,onAfterEnter:x},{default:()=>f}):f}function Re(e,n){return c(de,{ref:"addTabInstRef",key:"__addable",name:"__addable",internalCreatedByPane:!0,internalAddable:!0,internalLeftPadded:n,disabled:typeof e=="object"&&e.disabled})}function Te(e){const n=Ot(e);return n.props?n.props.internalLeftPadded=!0:n.props={internalLeftPadded:!0},n}function le(e){return Array.isArray(e.dynamicProps)?e.dynamicProps.includes("internalLeftPadded")||e.dynamicProps.push("internalLeftPadded"):e.dynamicProps=["internalLeftPadded"],e}export{la as _,da as a};
