import{V as Xe,bP as tn,aj as fn,d as ge,h as i,aK as hn,bQ as Je,aN as Ue,bu as Ce,N as Hn,ay as vn,c as x,a as M,ar as U,ao as ne,b0 as Ze,av as bn,b as Oe,u as en,e as gn,an as j,bR as Un,B as S,f as P,bS as qn,a2 as Fe,ad as pn,bm as Gn,H as be,by as Be,aV as on,bT as Yn,g as nn,r as ln,bL as Zn,bg as Qn,az as Xn,bU as Ie,bV as Jn,aO as et,bW as nt,a1 as qe,bX as an,a5 as tt,F as ot,bY as lt,aU as rn,bd as it,bZ as at,aT as rt,b2 as st,b_ as Qe,b$ as dt,c0 as ut,c1 as ct,Z as ft,af as ht,c2 as sn,c3 as vt,c4 as bt,aY as ee}from"./index-e99f5908.js";import{N as gt,u as pt}from"./Input-8cc4953e.js";import{V as mt,N as wt,g as dn}from"./Empty-7a4a7b1d.js";function Ge(e){const r=e.filter(s=>s!==void 0);if(r.length!==0)return r.length===1?r[0]:s=>{e.forEach(c=>{c&&c(s)})}}function mn(e,r){r&&(Xe(()=>{const{value:s}=e;s&&tn.registerHandler(s,r)}),fn(()=>{const{value:s}=e;s&&tn.unregisterHandler(s)}))}const yt=ge({name:"Checkmark",render(){return i("svg",{xmlns:"http://www.w3.org/2000/svg",viewBox:"0 0 16 16"},i("g",{fill:"none"},i("path",{d:"M14.046 3.486a.75.75 0 0 1-.032 1.06l-7.93 7.474a.85.85 0 0 1-1.188-.022l-2.68-2.72a.75.75 0 1 1 1.068-1.053l2.234 2.267l7.468-7.038a.75.75 0 0 1 1.06.032z",fill:"currentColor"})))}}),xt=ge({props:{onFocus:Function,onBlur:Function},setup(e){return()=>i("div",{style:"width: 0; height: 0",tabindex:0,onFocus:e.onFocus,onBlur:e.onBlur})}});function Ct(e,r){return i(vn,{name:"fade-in-scale-up-transition"},{default:()=>e?i(Hn,{clsPrefix:r,class:`${r}-base-select-option__check`},{default:()=>i(yt)}):null})}const un=ge({name:"NBaseSelectOption",props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(e){const{valueRef:r,pendingTmNodeRef:s,multipleRef:c,valueSetRef:f,renderLabelRef:v,renderOptionRef:h,labelFieldRef:a,valueFieldRef:k,showCheckmarkRef:E,nodePropsRef:F,handleOptionClick:A,handleOptionMouseEnter:R}=hn(Je),C=Ue(()=>{const{value:T}=s;return T?e.tmNode.key===T.key:!1});function w(T){const{tmNode:O}=e;O.disabled||A(T,O)}function _(T){const{tmNode:O}=e;O.disabled||R(T,O)}function W(T){const{tmNode:O}=e,{value:z}=C;O.disabled||z||R(T,O)}return{multiple:c,isGrouped:Ue(()=>{const{tmNode:T}=e,{parent:O}=T;return O&&O.rawNode.type==="group"}),showCheckmark:E,nodeProps:F,isPending:C,isSelected:Ue(()=>{const{value:T}=r,{value:O}=c;if(T===null)return!1;const z=e.tmNode.rawNode[k.value];if(O){const{value:D}=f;return D.has(z)}else return T===z}),labelField:a,renderLabel:v,renderOption:h,handleMouseMove:W,handleMouseEnter:_,handleClick:w}},render(){const{clsPrefix:e,tmNode:{rawNode:r},isSelected:s,isPending:c,isGrouped:f,showCheckmark:v,nodeProps:h,renderOption:a,renderLabel:k,handleClick:E,handleMouseEnter:F,handleMouseMove:A}=this,R=Ct(s,e),C=k?[k(r,s),v&&R]:[Ce(r[this.labelField],r,s),v&&R],w=h?.(r),_=i("div",Object.assign({},w,{class:[`${e}-base-select-option`,r.class,w?.class,{[`${e}-base-select-option--disabled`]:r.disabled,[`${e}-base-select-option--selected`]:s,[`${e}-base-select-option--grouped`]:f,[`${e}-base-select-option--pending`]:c,[`${e}-base-select-option--show-checkmark`]:v}],style:[w?.style||"",r.style||""],onClick:Ge([E,w?.onClick]),onMouseenter:Ge([F,w?.onMouseenter]),onMousemove:Ge([A,w?.onMousemove])}),i("div",{class:`${e}-base-select-option__content`},C));return r.render?r.render({node:_,option:r,selected:s}):a?a({node:_,option:r,selected:s}):_}}),cn=ge({name:"NBaseSelectGroupHeader",props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(){const{renderLabelRef:e,renderOptionRef:r,labelFieldRef:s,nodePropsRef:c}=hn(Je);return{labelField:s,nodeProps:c,renderLabel:e,renderOption:r}},render(){const{clsPrefix:e,renderLabel:r,renderOption:s,nodeProps:c,tmNode:{rawNode:f}}=this,v=c?.(f),h=r?r(f,!1):Ce(f[this.labelField],f,!1),a=i("div",Object.assign({},v,{class:[`${e}-base-select-group-header`,v?.class]}),h);return f.render?f.render({node:a,option:f}):s?s({node:a,option:f,selected:!1}):a}}),Ft=x("base-select-menu",`
 line-height: 1.5;
 outline: none;
 z-index: 0;
 position: relative;
 border-radius: var(--n-border-radius);
 transition:
 background-color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier);
 background-color: var(--n-color);
`,[x("scrollbar",`
 max-height: var(--n-height);
 `),x("virtual-list",`
 max-height: var(--n-height);
 `),x("base-select-option",`
 min-height: var(--n-option-height);
 font-size: var(--n-option-font-size);
 display: flex;
 align-items: center;
 `,[M("content",`
 z-index: 1;
 white-space: nowrap;
 text-overflow: ellipsis;
 overflow: hidden;
 `)]),x("base-select-group-header",`
 min-height: var(--n-option-height);
 font-size: .93em;
 display: flex;
 align-items: center;
 `),x("base-select-menu-option-wrapper",`
 position: relative;
 width: 100%;
 `),M("loading, empty",`
 display: flex;
 padding: 12px 32px;
 flex: 1;
 justify-content: center;
 `),M("loading",`
 color: var(--n-loading-color);
 font-size: var(--n-loading-size);
 `),M("header",`
 padding: 8px var(--n-option-padding-left);
 font-size: var(--n-option-font-size);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 border-bottom: 1px solid var(--n-action-divider-color);
 color: var(--n-action-text-color);
 `),M("action",`
 padding: 8px var(--n-option-padding-left);
 font-size: var(--n-option-font-size);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 border-top: 1px solid var(--n-action-divider-color);
 color: var(--n-action-text-color);
 `),x("base-select-group-header",`
 position: relative;
 cursor: default;
 padding: var(--n-option-padding);
 color: var(--n-group-header-text-color);
 `),x("base-select-option",`
 cursor: pointer;
 position: relative;
 padding: var(--n-option-padding);
 transition:
 color .3s var(--n-bezier),
 opacity .3s var(--n-bezier);
 box-sizing: border-box;
 color: var(--n-option-text-color);
 opacity: 1;
 `,[U("show-checkmark",`
 padding-right: calc(var(--n-option-padding-right) + 20px);
 `),ne("&::before",`
 content: "";
 position: absolute;
 left: 4px;
 right: 4px;
 top: 0;
 bottom: 0;
 border-radius: var(--n-border-radius);
 transition: background-color .3s var(--n-bezier);
 `),ne("&:active",`
 color: var(--n-option-text-color-pressed);
 `),U("grouped",`
 padding-left: calc(var(--n-option-padding-left) * 1.5);
 `),U("pending",[ne("&::before",`
 background-color: var(--n-option-color-pending);
 `)]),U("selected",`
 color: var(--n-option-text-color-active);
 `,[ne("&::before",`
 background-color: var(--n-option-color-active);
 `),U("pending",[ne("&::before",`
 background-color: var(--n-option-color-active-pending);
 `)])]),U("disabled",`
 cursor: not-allowed;
 `,[Ze("selected",`
 color: var(--n-option-text-color-disabled);
 `),U("selected",`
 opacity: var(--n-option-opacity-disabled);
 `)]),M("check",`
 font-size: 16px;
 position: absolute;
 right: calc(var(--n-option-padding-right) - 4px);
 top: calc(50% - 7px);
 color: var(--n-option-check-color);
 transition: color .3s var(--n-bezier);
 `,[bn({enterScale:"0.5"})])])]),Ot=ge({name:"InternalSelectMenu",props:Object.assign(Object.assign({},Oe.props),{clsPrefix:{type:String,required:!0},scrollable:{type:Boolean,default:!0},treeMate:{type:Object,required:!0},multiple:Boolean,size:{type:String,default:"medium"},value:{type:[String,Number,Array],default:null},autoPending:Boolean,virtualScroll:{type:Boolean,default:!0},show:{type:Boolean,default:!0},labelField:{type:String,default:"label"},valueField:{type:String,default:"value"},loading:Boolean,focusable:Boolean,renderLabel:Function,renderOption:Function,nodeProps:Function,showCheckmark:{type:Boolean,default:!0},onMousedown:Function,onScroll:Function,onFocus:Function,onBlur:Function,onKeyup:Function,onKeydown:Function,onTabOut:Function,onMouseenter:Function,onMouseleave:Function,onResize:Function,resetMenuOnOptionsChange:{type:Boolean,default:!0},inlineThemeDisabled:Boolean,onToggle:Function}),setup(e){const{mergedClsPrefixRef:r,mergedRtlRef:s}=en(e),c=gn("InternalSelectMenu",s,r),f=Oe("InternalSelectMenu","-internal-select-menu",Ft,Un,e,j(e,"clsPrefix")),v=S(null),h=S(null),a=S(null),k=P(()=>e.treeMate.getFlattenedNodes()),E=P(()=>qn(k.value)),F=S(null);function A(){const{treeMate:o}=e;let d=null;const{value:$}=e;$===null?d=o.getFirstAvailableNode():(e.multiple?d=o.getNode(($||[])[($||[]).length-1]):d=o.getNode($),(!d||d.disabled)&&(d=o.getFirstAvailableNode())),Q(d||null)}function R(){const{value:o}=F;o&&!e.treeMate.getNode(o.key)&&(F.value=null)}let C;Fe(()=>e.show,o=>{o?C=Fe(()=>e.treeMate,()=>{e.resetMenuOnOptionsChange?(e.autoPending?A():R(),pn(ce)):R()},{immediate:!0}):C?.()},{immediate:!0}),fn(()=>{C?.()});const w=P(()=>Gn(f.value.self[be("optionHeight",e.size)])),_=P(()=>Be(f.value.self[be("padding",e.size)])),W=P(()=>e.multiple&&Array.isArray(e.value)?new Set(e.value):new Set),T=P(()=>{const o=k.value;return o&&o.length===0});function O(o){const{onToggle:d}=e;d&&d(o)}function z(o){const{onScroll:d}=e;d&&d(o)}function D(o){var d;(d=a.value)===null||d===void 0||d.sync(),z(o)}function B(){var o;(o=a.value)===null||o===void 0||o.sync()}function G(){const{value:o}=F;return o||null}function q(o,d){d.disabled||Q(d,!1)}function de(o,d){d.disabled||O(d)}function ue(o){var d;Ie(o,"action")||(d=e.onKeyup)===null||d===void 0||d.call(e,o)}function Y(o){var d;Ie(o,"action")||(d=e.onKeydown)===null||d===void 0||d.call(e,o)}function Z(o){var d;(d=e.onMousedown)===null||d===void 0||d.call(e,o),!e.focusable&&o.preventDefault()}function te(){const{value:o}=F;o&&Q(o.getNext({loop:!0}),!0)}function I(){const{value:o}=F;o&&Q(o.getPrev({loop:!0}),!0)}function Q(o,d=!1){F.value=o,d&&ce()}function ce(){var o,d;const $=F.value;if(!$)return;const le=E.value($.key);le!==null&&(e.virtualScroll?(o=h.value)===null||o===void 0||o.scrollTo({index:le}):(d=a.value)===null||d===void 0||d.scrollTo({index:le,elSize:w.value}))}function ae(o){var d,$;!((d=v.value)===null||d===void 0)&&d.contains(o.target)&&(($=e.onFocus)===null||$===void 0||$.call(e,o))}function Se(o){var d,$;!((d=v.value)===null||d===void 0)&&d.contains(o.relatedTarget)||($=e.onBlur)===null||$===void 0||$.call(e,o)}on(Je,{handleOptionMouseEnter:q,handleOptionClick:de,valueSetRef:W,pendingTmNodeRef:F,nodePropsRef:j(e,"nodeProps"),showCheckmarkRef:j(e,"showCheckmark"),multipleRef:j(e,"multiple"),valueRef:j(e,"value"),renderLabelRef:j(e,"renderLabel"),renderOptionRef:j(e,"renderOption"),labelFieldRef:j(e,"labelField"),valueFieldRef:j(e,"valueField")}),on(Yn,v),Xe(()=>{const{value:o}=a;o&&o.sync()});const oe=P(()=>{const{size:o}=e,{common:{cubicBezierEaseInOut:d},self:{height:$,borderRadius:le,color:me,groupHeaderTextColor:we,actionDividerColor:ie,optionTextColorPressed:H,optionTextColor:ye,optionTextColorDisabled:re,optionTextColorActive:Re,optionOpacityDisabled:Te,optionCheckColor:Me,actionTextColor:Pe,optionColorPending:fe,optionColorActive:he,loadingColor:ke,loadingSize:ze,optionColorActivePending:_e,[be("optionFontSize",o)]:xe,[be("optionHeight",o)]:ve,[be("optionPadding",o)]:V}}=f.value;return{"--n-height":$,"--n-action-divider-color":ie,"--n-action-text-color":Pe,"--n-bezier":d,"--n-border-radius":le,"--n-color":me,"--n-option-font-size":xe,"--n-group-header-text-color":we,"--n-option-check-color":Me,"--n-option-color-pending":fe,"--n-option-color-active":he,"--n-option-color-active-pending":_e,"--n-option-height":ve,"--n-option-opacity-disabled":Te,"--n-option-text-color":ye,"--n-option-text-color-active":Re,"--n-option-text-color-disabled":re,"--n-option-text-color-pressed":H,"--n-option-padding":V,"--n-option-padding-left":Be(V,"left"),"--n-option-padding-right":Be(V,"right"),"--n-loading-color":ke,"--n-loading-size":ze}}),{inlineThemeDisabled:pe}=e,K=pe?nn("internal-select-menu",P(()=>e.size[0]),oe,e):void 0,X={selfRef:v,next:te,prev:I,getPendingTmNode:G};return mn(v,e.onResize),Object.assign({mergedTheme:f,mergedClsPrefix:r,rtlEnabled:c,virtualListRef:h,scrollbarRef:a,itemSize:w,padding:_,flattenedNodes:k,empty:T,virtualListContainer(){const{value:o}=h;return o?.listElRef},virtualListContent(){const{value:o}=h;return o?.itemsElRef},doScroll:z,handleFocusin:ae,handleFocusout:Se,handleKeyUp:ue,handleKeyDown:Y,handleMouseDown:Z,handleVirtualListResize:B,handleVirtualListScroll:D,cssVars:pe?void 0:oe,themeClass:K?.themeClass,onRender:K?.onRender},X)},render(){const{$slots:e,virtualScroll:r,clsPrefix:s,mergedTheme:c,themeClass:f,onRender:v}=this;return v?.(),i("div",{ref:"selfRef",tabindex:this.focusable?0:-1,class:[`${s}-base-select-menu`,this.rtlEnabled&&`${s}-base-select-menu--rtl`,f,this.multiple&&`${s}-base-select-menu--multiple`],style:this.cssVars,onFocusin:this.handleFocusin,onFocusout:this.handleFocusout,onKeyup:this.handleKeyUp,onKeydown:this.handleKeyDown,onMousedown:this.handleMouseDown,onMouseenter:this.onMouseenter,onMouseleave:this.onMouseleave},ln(e.header,h=>h&&i("div",{class:`${s}-base-select-menu__header`,"data-header":!0,key:"header"},h)),this.loading?i("div",{class:`${s}-base-select-menu__loading`},i(Zn,{clsPrefix:s,strokeWidth:20})):this.empty?i("div",{class:`${s}-base-select-menu__empty`,"data-empty":!0},Xn(e.empty,()=>[i(wt,{theme:c.peers.Empty,themeOverrides:c.peerOverrides.Empty})])):i(Qn,{ref:"scrollbarRef",theme:c.peers.Scrollbar,themeOverrides:c.peerOverrides.Scrollbar,scrollable:this.scrollable,container:r?this.virtualListContainer:void 0,content:r?this.virtualListContent:void 0,onScroll:r?void 0:this.doScroll},{default:()=>r?i(mt,{ref:"virtualListRef",class:`${s}-virtual-list`,items:this.flattenedNodes,itemSize:this.itemSize,showScrollbar:!1,paddingTop:this.padding.top,paddingBottom:this.padding.bottom,onResize:this.handleVirtualListResize,onScroll:this.handleVirtualListScroll,itemResizable:!0},{default:({item:h})=>h.isGroup?i(cn,{key:h.key,clsPrefix:s,tmNode:h}):h.ignored?null:i(un,{clsPrefix:s,key:h.key,tmNode:h})}):i("div",{class:`${s}-base-select-menu-option-wrapper`,style:{paddingTop:this.padding.top,paddingBottom:this.padding.bottom}},this.flattenedNodes.map(h=>h.isGroup?i(cn,{key:h.key,clsPrefix:s,tmNode:h}):i(un,{clsPrefix:s,key:h.key,tmNode:h})))}),ln(e.action,h=>h&&[i("div",{class:`${s}-base-select-menu__action`,"data-action":!0,key:"action"},h),i(xt,{onFocus:this.onTabOut,key:"focus-detector"})]))}}),St=ne([x("base-selection",`
 --n-padding-single: var(--n-padding-single-top) var(--n-padding-single-right) var(--n-padding-single-bottom) var(--n-padding-single-left);
 --n-padding-multiple: var(--n-padding-multiple-top) var(--n-padding-multiple-right) var(--n-padding-multiple-bottom) var(--n-padding-multiple-left);
 position: relative;
 z-index: auto;
 box-shadow: none;
 width: 100%;
 max-width: 100%;
 display: inline-block;
 vertical-align: bottom;
 border-radius: var(--n-border-radius);
 min-height: var(--n-height);
 line-height: 1.5;
 font-size: var(--n-font-size);
 `,[x("base-loading",`
 color: var(--n-loading-color);
 `),x("base-selection-tags","min-height: var(--n-height);"),M("border, state-border",`
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 pointer-events: none;
 border: var(--n-border);
 border-radius: inherit;
 transition:
 box-shadow .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `),M("state-border",`
 z-index: 1;
 border-color: #0000;
 `),x("base-suffix",`
 cursor: pointer;
 position: absolute;
 top: 50%;
 transform: translateY(-50%);
 right: 10px;
 `,[M("arrow",`
 font-size: var(--n-arrow-size);
 color: var(--n-arrow-color);
 transition: color .3s var(--n-bezier);
 `)]),x("base-selection-overlay",`
 display: flex;
 align-items: center;
 white-space: nowrap;
 pointer-events: none;
 position: absolute;
 top: 0;
 right: 0;
 bottom: 0;
 left: 0;
 padding: var(--n-padding-single);
 transition: color .3s var(--n-bezier);
 `,[M("wrapper",`
 flex-basis: 0;
 flex-grow: 1;
 overflow: hidden;
 text-overflow: ellipsis;
 `)]),x("base-selection-placeholder",`
 color: var(--n-placeholder-color);
 `,[M("inner",`
 max-width: 100%;
 overflow: hidden;
 `)]),x("base-selection-tags",`
 cursor: pointer;
 outline: none;
 box-sizing: border-box;
 position: relative;
 z-index: auto;
 display: flex;
 padding: var(--n-padding-multiple);
 flex-wrap: wrap;
 align-items: center;
 width: 100%;
 vertical-align: bottom;
 background-color: var(--n-color);
 border-radius: inherit;
 transition:
 color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 `),x("base-selection-label",`
 height: var(--n-height);
 display: inline-flex;
 width: 100%;
 vertical-align: bottom;
 cursor: pointer;
 outline: none;
 z-index: auto;
 box-sizing: border-box;
 position: relative;
 transition:
 color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 border-radius: inherit;
 background-color: var(--n-color);
 align-items: center;
 `,[x("base-selection-input",`
 font-size: inherit;
 line-height: inherit;
 outline: none;
 cursor: pointer;
 box-sizing: border-box;
 border:none;
 width: 100%;
 padding: var(--n-padding-single);
 background-color: #0000;
 color: var(--n-text-color);
 transition: color .3s var(--n-bezier);
 caret-color: var(--n-caret-color);
 `,[M("content",`
 text-overflow: ellipsis;
 overflow: hidden;
 white-space: nowrap; 
 `)]),M("render-label",`
 color: var(--n-text-color);
 `)]),Ze("disabled",[ne("&:hover",[M("state-border",`
 box-shadow: var(--n-box-shadow-hover);
 border: var(--n-border-hover);
 `)]),U("focus",[M("state-border",`
 box-shadow: var(--n-box-shadow-focus);
 border: var(--n-border-focus);
 `)]),U("active",[M("state-border",`
 box-shadow: var(--n-box-shadow-active);
 border: var(--n-border-active);
 `),x("base-selection-label","background-color: var(--n-color-active);"),x("base-selection-tags","background-color: var(--n-color-active);")])]),U("disabled","cursor: not-allowed;",[M("arrow",`
 color: var(--n-arrow-color-disabled);
 `),x("base-selection-label",`
 cursor: not-allowed;
 background-color: var(--n-color-disabled);
 `,[x("base-selection-input",`
 cursor: not-allowed;
 color: var(--n-text-color-disabled);
 `),M("render-label",`
 color: var(--n-text-color-disabled);
 `)]),x("base-selection-tags",`
 cursor: not-allowed;
 background-color: var(--n-color-disabled);
 `),x("base-selection-placeholder",`
 cursor: not-allowed;
 color: var(--n-placeholder-color-disabled);
 `)]),x("base-selection-input-tag",`
 height: calc(var(--n-height) - 6px);
 line-height: calc(var(--n-height) - 6px);
 outline: none;
 display: none;
 position: relative;
 margin-bottom: 3px;
 max-width: 100%;
 vertical-align: bottom;
 `,[M("input",`
 font-size: inherit;
 font-family: inherit;
 min-width: 1px;
 padding: 0;
 background-color: #0000;
 outline: none;
 border: none;
 max-width: 100%;
 overflow: hidden;
 width: 1em;
 line-height: inherit;
 cursor: pointer;
 color: var(--n-text-color);
 caret-color: var(--n-caret-color);
 `),M("mirror",`
 position: absolute;
 left: 0;
 top: 0;
 white-space: pre;
 visibility: hidden;
 user-select: none;
 -webkit-user-select: none;
 opacity: 0;
 `)]),["warning","error"].map(e=>U(`${e}-status`,[M("state-border",`border: var(--n-border-${e});`),Ze("disabled",[ne("&:hover",[M("state-border",`
 box-shadow: var(--n-box-shadow-hover-${e});
 border: var(--n-border-hover-${e});
 `)]),U("active",[M("state-border",`
 box-shadow: var(--n-box-shadow-active-${e});
 border: var(--n-border-active-${e});
 `),x("base-selection-label",`background-color: var(--n-color-active-${e});`),x("base-selection-tags",`background-color: var(--n-color-active-${e});`)]),U("focus",[M("state-border",`
 box-shadow: var(--n-box-shadow-focus-${e});
 border: var(--n-border-focus-${e});
 `)])])]))]),x("base-selection-popover",`
 margin-bottom: -3px;
 display: flex;
 flex-wrap: wrap;
 margin-right: -8px;
 `),x("base-selection-tag-wrapper",`
 max-width: 100%;
 display: inline-flex;
 padding: 0 7px 3px 0;
 `,[ne("&:last-child","padding-right: 0;"),x("tag",`
 font-size: 14px;
 max-width: 100%;
 `,[M("content",`
 line-height: 1.25;
 text-overflow: ellipsis;
 overflow: hidden;
 `)])])]),Rt=ge({name:"InternalSelection",props:Object.assign(Object.assign({},Oe.props),{clsPrefix:{type:String,required:!0},bordered:{type:Boolean,default:void 0},active:Boolean,pattern:{type:String,default:""},placeholder:String,selectedOption:{type:Object,default:null},selectedOptions:{type:Array,default:null},labelField:{type:String,default:"label"},valueField:{type:String,default:"value"},multiple:Boolean,filterable:Boolean,clearable:Boolean,disabled:Boolean,size:{type:String,default:"medium"},loading:Boolean,autofocus:Boolean,showArrow:{type:Boolean,default:!0},inputProps:Object,focused:Boolean,renderTag:Function,onKeydown:Function,onClick:Function,onBlur:Function,onFocus:Function,onDeleteOption:Function,maxTagCount:[String,Number],ellipsisTagPopoverProps:Object,onClear:Function,onPatternInput:Function,onPatternFocus:Function,onPatternBlur:Function,renderLabel:Function,status:String,inlineThemeDisabled:Boolean,ignoreComposition:{type:Boolean,default:!0},onResize:Function}),setup(e){const{mergedClsPrefixRef:r,mergedRtlRef:s}=en(e),c=gn("InternalSelection",s,r),f=S(null),v=S(null),h=S(null),a=S(null),k=S(null),E=S(null),F=S(null),A=S(null),R=S(null),C=S(null),w=S(!1),_=S(!1),W=S(!1),T=Oe("InternalSelection","-internal-selection",St,Jn,e,j(e,"clsPrefix")),O=P(()=>e.clearable&&!e.disabled&&(W.value||e.active)),z=P(()=>e.selectedOption?e.renderTag?e.renderTag({option:e.selectedOption,handleClose:()=>{}}):e.renderLabel?e.renderLabel(e.selectedOption,!0):Ce(e.selectedOption[e.labelField],e.selectedOption,!0):e.placeholder),D=P(()=>{const t=e.selectedOption;if(t)return t[e.labelField]}),B=P(()=>e.multiple?!!(Array.isArray(e.selectedOptions)&&e.selectedOptions.length):e.selectedOption!==null);function G(){var t;const{value:u}=f;if(u){const{value:N}=v;N&&(N.style.width=`${u.offsetWidth}px`,e.maxTagCount!=="responsive"&&((t=R.value)===null||t===void 0||t.sync({showAllItemsBeforeCalculate:!1})))}}function q(){const{value:t}=C;t&&(t.style.display="none")}function de(){const{value:t}=C;t&&(t.style.display="inline-block")}Fe(j(e,"active"),t=>{t||q()}),Fe(j(e,"pattern"),()=>{e.multiple&&pn(G)});function ue(t){const{onFocus:u}=e;u&&u(t)}function Y(t){const{onBlur:u}=e;u&&u(t)}function Z(t){const{onDeleteOption:u}=e;u&&u(t)}function te(t){const{onClear:u}=e;u&&u(t)}function I(t){const{onPatternInput:u}=e;u&&u(t)}function Q(t){var u;(!t.relatedTarget||!(!((u=h.value)===null||u===void 0)&&u.contains(t.relatedTarget)))&&ue(t)}function ce(t){var u;!((u=h.value)===null||u===void 0)&&u.contains(t.relatedTarget)||Y(t)}function ae(t){te(t)}function Se(){W.value=!0}function oe(){W.value=!1}function pe(t){!e.active||!e.filterable||t.target!==v.value&&t.preventDefault()}function K(t){Z(t)}const X=S(!1);function o(t){if(t.key==="Backspace"&&!X.value&&!e.pattern.length){const{selectedOptions:u}=e;u?.length&&K(u[u.length-1])}}let d=null;function $(t){const{value:u}=f;if(u){const N=t.target.value;u.textContent=N,G()}e.ignoreComposition&&X.value?d=t:I(t)}function le(){X.value=!0}function me(){X.value=!1,e.ignoreComposition&&I(d),d=null}function we(t){var u;_.value=!0,(u=e.onPatternFocus)===null||u===void 0||u.call(e,t)}function ie(t){var u;_.value=!1,(u=e.onPatternBlur)===null||u===void 0||u.call(e,t)}function H(){var t,u;if(e.filterable)_.value=!1,(t=E.value)===null||t===void 0||t.blur(),(u=v.value)===null||u===void 0||u.blur();else if(e.multiple){const{value:N}=a;N?.blur()}else{const{value:N}=k;N?.blur()}}function ye(){var t,u,N;e.filterable?(_.value=!1,(t=E.value)===null||t===void 0||t.focus()):e.multiple?(u=a.value)===null||u===void 0||u.focus():(N=k.value)===null||N===void 0||N.focus()}function re(){const{value:t}=v;t&&(de(),t.focus())}function Re(){const{value:t}=v;t&&t.blur()}function Te(t){const{value:u}=F;u&&u.setTextContent(`+${t}`)}function Me(){const{value:t}=A;return t}function Pe(){return v.value}let fe=null;function he(){fe!==null&&window.clearTimeout(fe)}function ke(){e.active||(he(),fe=window.setTimeout(()=>{B.value&&(w.value=!0)},100))}function ze(){he()}function _e(t){t||(he(),w.value=!1)}Fe(B,t=>{t||(w.value=!1)}),Xe(()=>{et(()=>{const t=E.value;t&&(e.disabled?t.removeAttribute("tabindex"):t.tabIndex=_.value?-1:0)})}),mn(h,e.onResize);const{inlineThemeDisabled:xe}=e,ve=P(()=>{const{size:t}=e,{common:{cubicBezierEaseInOut:u},self:{borderRadius:N,color:je,placeholderColor:We,textColor:$e,paddingSingle:Ee,paddingMultiple:Ne,caretColor:Ke,colorDisabled:He,textColorDisabled:Ae,placeholderColorDisabled:se,colorActive:n,boxShadowFocus:l,boxShadowActive:b,boxShadowHover:y,border:p,borderFocus:g,borderHover:m,borderActive:L,arrowColor:J,arrowColorDisabled:yn,loadingColor:xn,colorActiveWarning:Cn,boxShadowFocusWarning:Fn,boxShadowActiveWarning:On,boxShadowHoverWarning:Sn,borderWarning:Rn,borderFocusWarning:Tn,borderHoverWarning:Mn,borderActiveWarning:Pn,colorActiveError:kn,boxShadowFocusError:zn,boxShadowActiveError:_n,boxShadowHoverError:Bn,borderError:In,borderFocusError:$n,borderHoverError:En,borderActiveError:Nn,clearColor:An,clearColorHover:Dn,clearColorPressed:Ln,clearSize:Vn,arrowSize:jn,[be("height",t)]:Wn,[be("fontSize",t)]:Kn}}=T.value,De=Be(Ee),Le=Be(Ne);return{"--n-bezier":u,"--n-border":p,"--n-border-active":L,"--n-border-focus":g,"--n-border-hover":m,"--n-border-radius":N,"--n-box-shadow-active":b,"--n-box-shadow-focus":l,"--n-box-shadow-hover":y,"--n-caret-color":Ke,"--n-color":je,"--n-color-active":n,"--n-color-disabled":He,"--n-font-size":Kn,"--n-height":Wn,"--n-padding-single-top":De.top,"--n-padding-multiple-top":Le.top,"--n-padding-single-right":De.right,"--n-padding-multiple-right":Le.right,"--n-padding-single-left":De.left,"--n-padding-multiple-left":Le.left,"--n-padding-single-bottom":De.bottom,"--n-padding-multiple-bottom":Le.bottom,"--n-placeholder-color":We,"--n-placeholder-color-disabled":se,"--n-text-color":$e,"--n-text-color-disabled":Ae,"--n-arrow-color":J,"--n-arrow-color-disabled":yn,"--n-loading-color":xn,"--n-color-active-warning":Cn,"--n-box-shadow-focus-warning":Fn,"--n-box-shadow-active-warning":On,"--n-box-shadow-hover-warning":Sn,"--n-border-warning":Rn,"--n-border-focus-warning":Tn,"--n-border-hover-warning":Mn,"--n-border-active-warning":Pn,"--n-color-active-error":kn,"--n-box-shadow-focus-error":zn,"--n-box-shadow-active-error":_n,"--n-box-shadow-hover-error":Bn,"--n-border-error":In,"--n-border-focus-error":$n,"--n-border-hover-error":En,"--n-border-active-error":Nn,"--n-clear-size":Vn,"--n-clear-color":An,"--n-clear-color-hover":Dn,"--n-clear-color-pressed":Ln,"--n-arrow-size":jn}}),V=xe?nn("internal-selection",P(()=>e.size[0]),ve,e):void 0;return{mergedTheme:T,mergedClearable:O,mergedClsPrefix:r,rtlEnabled:c,patternInputFocused:_,filterablePlaceholder:z,label:D,selected:B,showTagsPanel:w,isComposing:X,counterRef:F,counterWrapperRef:A,patternInputMirrorRef:f,patternInputRef:v,selfRef:h,multipleElRef:a,singleElRef:k,patternInputWrapperRef:E,overflowRef:R,inputTagElRef:C,handleMouseDown:pe,handleFocusin:Q,handleClear:ae,handleMouseEnter:Se,handleMouseLeave:oe,handleDeleteOption:K,handlePatternKeyDown:o,handlePatternInputInput:$,handlePatternInputBlur:ie,handlePatternInputFocus:we,handleMouseEnterCounter:ke,handleMouseLeaveCounter:ze,handleFocusout:ce,handleCompositionEnd:me,handleCompositionStart:le,onPopoverUpdateShow:_e,focus:ye,focusInput:re,blur:H,blurInput:Re,updateCounter:Te,getCounter:Me,getTail:Pe,renderLabel:e.renderLabel,cssVars:xe?void 0:ve,themeClass:V?.themeClass,onRender:V?.onRender}},render(){const{status:e,multiple:r,size:s,disabled:c,filterable:f,maxTagCount:v,bordered:h,clsPrefix:a,ellipsisTagPopoverProps:k,onRender:E,renderTag:F,renderLabel:A}=this;E?.();const R=v==="responsive",C=typeof v=="number",w=R||C,_=i(nt,null,{default:()=>i(gt,{clsPrefix:a,loading:this.loading,showArrow:this.showArrow,showClear:this.mergedClearable&&this.selected,onClear:this.handleClear},{default:()=>{var T,O;return(O=(T=this.$slots).arrow)===null||O===void 0?void 0:O.call(T)}})});let W;if(r){const{labelField:T}=this,O=I=>i("div",{class:`${a}-base-selection-tag-wrapper`,key:I.value},F?F({option:I,handleClose:()=>{this.handleDeleteOption(I)}}):i(qe,{size:s,closable:!I.disabled,disabled:c,onClose:()=>{this.handleDeleteOption(I)},internalCloseIsButtonTag:!1,internalCloseFocusable:!1},{default:()=>A?A(I,!0):Ce(I[T],I,!0)})),z=()=>(C?this.selectedOptions.slice(0,v):this.selectedOptions).map(O),D=f?i("div",{class:`${a}-base-selection-input-tag`,ref:"inputTagElRef",key:"__input-tag__"},i("input",Object.assign({},this.inputProps,{ref:"patternInputRef",tabindex:-1,disabled:c,value:this.pattern,autofocus:this.autofocus,class:`${a}-base-selection-input-tag__input`,onBlur:this.handlePatternInputBlur,onFocus:this.handlePatternInputFocus,onKeydown:this.handlePatternKeyDown,onInput:this.handlePatternInputInput,onCompositionstart:this.handleCompositionStart,onCompositionend:this.handleCompositionEnd})),i("span",{ref:"patternInputMirrorRef",class:`${a}-base-selection-input-tag__mirror`},this.pattern)):null,B=R?()=>i("div",{class:`${a}-base-selection-tag-wrapper`,ref:"counterWrapperRef"},i(qe,{size:s,ref:"counterRef",onMouseenter:this.handleMouseEnterCounter,onMouseleave:this.handleMouseLeaveCounter,disabled:c})):void 0;let G;if(C){const I=this.selectedOptions.length-v;I>0&&(G=i("div",{class:`${a}-base-selection-tag-wrapper`,key:"__counter__"},i(qe,{size:s,ref:"counterRef",onMouseenter:this.handleMouseEnterCounter,disabled:c},{default:()=>`+${I}`})))}const q=R?f?i(an,{ref:"overflowRef",updateCounter:this.updateCounter,getCounter:this.getCounter,getTail:this.getTail,style:{width:"100%",display:"flex",overflow:"hidden"}},{default:z,counter:B,tail:()=>D}):i(an,{ref:"overflowRef",updateCounter:this.updateCounter,getCounter:this.getCounter,style:{width:"100%",display:"flex",overflow:"hidden"}},{default:z,counter:B}):C&&G?z().concat(G):z(),de=w?()=>i("div",{class:`${a}-base-selection-popover`},R?z():this.selectedOptions.map(O)):void 0,ue=w?Object.assign({show:this.showTagsPanel,trigger:"hover",overlap:!0,placement:"top",width:"trigger",onUpdateShow:this.onPopoverUpdateShow,theme:this.mergedTheme.peers.Popover,themeOverrides:this.mergedTheme.peerOverrides.Popover},k):null,Z=(this.selected?!1:this.active?!this.pattern&&!this.isComposing:!0)?i("div",{class:`${a}-base-selection-placeholder ${a}-base-selection-overlay`},i("div",{class:`${a}-base-selection-placeholder__inner`},this.placeholder)):null,te=f?i("div",{ref:"patternInputWrapperRef",class:`${a}-base-selection-tags`},q,R?null:D,_):i("div",{ref:"multipleElRef",class:`${a}-base-selection-tags`,tabindex:c?void 0:0},q,_);W=i(ot,null,w?i(tt,Object.assign({},ue,{scrollable:!0,style:"max-height: calc(var(--v-target-height) * 6.6);"}),{trigger:()=>te,default:de}):te,Z)}else if(f){const T=this.pattern||this.isComposing,O=this.active?!T:!this.selected,z=this.active?!1:this.selected;W=i("div",{ref:"patternInputWrapperRef",class:`${a}-base-selection-label`,title:this.patternInputFocused?void 0:dn(this.label)},i("input",Object.assign({},this.inputProps,{ref:"patternInputRef",class:`${a}-base-selection-input`,value:this.active?this.pattern:"",placeholder:"",readonly:c,disabled:c,tabindex:-1,autofocus:this.autofocus,onFocus:this.handlePatternInputFocus,onBlur:this.handlePatternInputBlur,onInput:this.handlePatternInputInput,onCompositionstart:this.handleCompositionStart,onCompositionend:this.handleCompositionEnd})),z?i("div",{class:`${a}-base-selection-label__render-label ${a}-base-selection-overlay`,key:"input"},i("div",{class:`${a}-base-selection-overlay__wrapper`},F?F({option:this.selectedOption,handleClose:()=>{}}):A?A(this.selectedOption,!0):Ce(this.label,this.selectedOption,!0))):null,O?i("div",{class:`${a}-base-selection-placeholder ${a}-base-selection-overlay`,key:"placeholder"},i("div",{class:`${a}-base-selection-overlay__wrapper`},this.filterablePlaceholder)):null,_)}else W=i("div",{ref:"singleElRef",class:`${a}-base-selection-label`,tabindex:this.disabled?void 0:0},this.label!==void 0?i("div",{class:`${a}-base-selection-input`,title:dn(this.label),key:"input"},i("div",{class:`${a}-base-selection-input__content`},F?F({option:this.selectedOption,handleClose:()=>{}}):A?A(this.selectedOption,!0):Ce(this.label,this.selectedOption,!0))):i("div",{class:`${a}-base-selection-placeholder ${a}-base-selection-overlay`,key:"placeholder"},i("div",{class:`${a}-base-selection-placeholder__inner`},this.placeholder)),_);return i("div",{ref:"selfRef",class:[`${a}-base-selection`,this.rtlEnabled&&`${a}-base-selection--rtl`,this.themeClass,e&&`${a}-base-selection--${e}-status`,{[`${a}-base-selection--active`]:this.active,[`${a}-base-selection--selected`]:this.selected||this.active&&this.pattern,[`${a}-base-selection--disabled`]:this.disabled,[`${a}-base-selection--multiple`]:this.multiple,[`${a}-base-selection--focus`]:this.focused}],style:this.cssVars,onClick:this.onClick,onMouseenter:this.handleMouseEnter,onMouseleave:this.handleMouseLeave,onKeydown:this.onKeydown,onFocusin:this.handleFocusin,onFocusout:this.handleFocusout,onMousedown:this.handleMouseDown},W,h?i("div",{class:`${a}-base-selection__border`}):null,h?i("div",{class:`${a}-base-selection__state-border`}):null)}});function Ve(e){return e.type==="group"}function wn(e){return e.type==="ignored"}function Ye(e,r){try{return!!(1+r.toString().toLowerCase().indexOf(e.trim().toLowerCase()))}catch{return!1}}function Tt(e,r){return{getIsGroup:Ve,getIgnored:wn,getKey(c){return Ve(c)?c.name||c.key||"key-required":c[e]},getChildren(c){return c[r]}}}function Mt(e,r,s,c){if(!r)return e;function f(v){if(!Array.isArray(v))return[];const h=[];for(const a of v)if(Ve(a)){const k=f(a[c]);k.length&&h.push(Object.assign({},a,{[c]:k}))}else{if(wn(a))continue;r(s,a)&&h.push(a)}return h}return f(e)}function Pt(e,r,s){const c=new Map;return e.forEach(f=>{Ve(f)?f[s].forEach(v=>{c.set(v[r],v)}):c.set(f[r],f)}),c}const kt=ne([x("select",`
 z-index: auto;
 outline: none;
 width: 100%;
 position: relative;
 `),x("select-menu",`
 margin: 4px 0;
 box-shadow: var(--n-menu-box-shadow);
 `,[bn({originalTransition:"background-color .3s var(--n-bezier), box-shadow .3s var(--n-bezier)"})])]),zt=Object.assign(Object.assign({},Oe.props),{to:Qe.propTo,bordered:{type:Boolean,default:void 0},clearable:Boolean,clearFilterAfterSelect:{type:Boolean,default:!0},options:{type:Array,default:()=>[]},defaultValue:{type:[String,Number,Array],default:null},keyboard:{type:Boolean,default:!0},value:[String,Number,Array],placeholder:String,menuProps:Object,multiple:Boolean,size:String,filterable:Boolean,disabled:{type:Boolean,default:void 0},remote:Boolean,loading:Boolean,filter:Function,placement:{type:String,default:"bottom-start"},widthMode:{type:String,default:"trigger"},tag:Boolean,onCreate:Function,fallbackOption:{type:[Function,Boolean],default:void 0},show:{type:Boolean,default:void 0},showArrow:{type:Boolean,default:!0},maxTagCount:[Number,String],ellipsisTagPopoverProps:Object,consistentMenuWidth:{type:Boolean,default:!0},virtualScroll:{type:Boolean,default:!0},labelField:{type:String,default:"label"},valueField:{type:String,default:"value"},childrenField:{type:String,default:"children"},renderLabel:Function,renderOption:Function,renderTag:Function,"onUpdate:value":[Function,Array],inputProps:Object,nodeProps:Function,ignoreComposition:{type:Boolean,default:!0},showOnFocus:Boolean,onUpdateValue:[Function,Array],onBlur:[Function,Array],onClear:[Function,Array],onFocus:[Function,Array],onScroll:[Function,Array],onSearch:[Function,Array],onUpdateShow:[Function,Array],"onUpdate:show":[Function,Array],displayDirective:{type:String,default:"show"},resetMenuOnOptionsChange:{type:Boolean,default:!0},status:String,showCheckmark:{type:Boolean,default:!0},onChange:[Function,Array],items:Array}),$t=ge({name:"Select",props:zt,setup(e){const{mergedClsPrefixRef:r,mergedBorderedRef:s,namespaceRef:c,inlineThemeDisabled:f}=en(e),v=Oe("Select","-select",kt,lt,e,r),h=S(e.defaultValue),a=j(e,"value"),k=rn(a,h),E=S(!1),F=S(""),A=it(e,["items","options"]),R=S([]),C=S([]),w=P(()=>C.value.concat(R.value).concat(A.value)),_=P(()=>{const{filter:n}=e;if(n)return n;const{labelField:l,valueField:b}=e;return(y,p)=>{if(!p)return!1;const g=p[l];if(typeof g=="string")return Ye(y,g);const m=p[b];return typeof m=="string"?Ye(y,m):typeof m=="number"?Ye(y,String(m)):!1}}),W=P(()=>{if(e.remote)return A.value;{const{value:n}=w,{value:l}=F;return!l.length||!e.filterable?n:Mt(n,_.value,l,e.childrenField)}}),T=P(()=>{const{valueField:n,childrenField:l}=e,b=Tt(n,l);return at(W.value,b)}),O=P(()=>Pt(w.value,e.valueField,e.childrenField)),z=S(!1),D=rn(j(e,"show"),z),B=S(null),G=S(null),q=S(null),{localeRef:de}=pt("Select"),ue=P(()=>{var n;return(n=e.placeholder)!==null&&n!==void 0?n:de.value.placeholder}),Y=[],Z=S(new Map),te=P(()=>{const{fallbackOption:n}=e;if(n===void 0){const{labelField:l,valueField:b}=e;return y=>({[l]:String(y),[b]:y})}return n===!1?!1:l=>Object.assign(n(l),{value:l})});function I(n){const l=e.remote,{value:b}=Z,{value:y}=O,{value:p}=te,g=[];return n.forEach(m=>{if(y.has(m))g.push(y.get(m));else if(l&&b.has(m))g.push(b.get(m));else if(p){const L=p(m);L&&g.push(L)}}),g}const Q=P(()=>{if(e.multiple){const{value:n}=k;return Array.isArray(n)?I(n):[]}return null}),ce=P(()=>{const{value:n}=k;return!e.multiple&&!Array.isArray(n)?n===null?null:I([n])[0]||null:null}),ae=rt(e),{mergedSizeRef:Se,mergedDisabledRef:oe,mergedStatusRef:pe}=ae;function K(n,l){const{onChange:b,"onUpdate:value":y,onUpdateValue:p}=e,{nTriggerFormChange:g,nTriggerFormInput:m}=ae;b&&ee(b,n,l),p&&ee(p,n,l),y&&ee(y,n,l),h.value=n,g(),m()}function X(n){const{onBlur:l}=e,{nTriggerFormBlur:b}=ae;l&&ee(l,n),b()}function o(){const{onClear:n}=e;n&&ee(n)}function d(n){const{onFocus:l,showOnFocus:b}=e,{nTriggerFormFocus:y}=ae;l&&ee(l,n),y(),b&&ie()}function $(n){const{onSearch:l}=e;l&&ee(l,n)}function le(n){const{onScroll:l}=e;l&&ee(l,n)}function me(){var n;const{remote:l,multiple:b}=e;if(l){const{value:y}=Z;if(b){const{valueField:p}=e;(n=Q.value)===null||n===void 0||n.forEach(g=>{y.set(g[p],g)})}else{const p=ce.value;p&&y.set(p[e.valueField],p)}}}function we(n){const{onUpdateShow:l,"onUpdate:show":b}=e;l&&ee(l,n),b&&ee(b,n),z.value=n}function ie(){oe.value||(we(!0),z.value=!0,e.filterable&&Ne())}function H(){we(!1)}function ye(){F.value="",C.value=Y}const re=S(!1);function Re(){e.filterable&&(re.value=!0)}function Te(){e.filterable&&(re.value=!1,D.value||ye())}function Me(){oe.value||(D.value?e.filterable?Ne():H():ie())}function Pe(n){var l,b;!((b=(l=q.value)===null||l===void 0?void 0:l.selfRef)===null||b===void 0)&&b.contains(n.relatedTarget)||(E.value=!1,X(n),H())}function fe(n){d(n),E.value=!0}function he(){E.value=!0}function ke(n){var l;!((l=B.value)===null||l===void 0)&&l.$el.contains(n.relatedTarget)||(E.value=!1,X(n),H())}function ze(){var n;(n=B.value)===null||n===void 0||n.focus(),H()}function _e(n){var l;D.value&&(!((l=B.value)===null||l===void 0)&&l.$el.contains(vt(n))||H())}function xe(n){if(!Array.isArray(n))return[];if(te.value)return Array.from(n);{const{remote:l}=e,{value:b}=O;if(l){const{value:y}=Z;return n.filter(p=>b.has(p)||y.has(p))}else return n.filter(y=>b.has(y))}}function ve(n){V(n.rawNode)}function V(n){if(oe.value)return;const{tag:l,remote:b,clearFilterAfterSelect:y,valueField:p}=e;if(l&&!b){const{value:g}=C,m=g[0]||null;if(m){const L=R.value;L.length?L.push(m):R.value=[m],C.value=Y}}if(b&&Z.value.set(n[p],n),e.multiple){const g=xe(k.value),m=g.findIndex(L=>L===n[p]);if(~m){if(g.splice(m,1),l&&!b){const L=t(n[p]);~L&&(R.value.splice(L,1),y&&(F.value=""))}}else g.push(n[p]),y&&(F.value="");K(g,I(g))}else{if(l&&!b){const g=t(n[p]);~g?R.value=[R.value[g]]:R.value=Y}Ee(),H(),K(n[p],n)}}function t(n){return R.value.findIndex(b=>b[e.valueField]===n)}function u(n){D.value||ie();const{value:l}=n.target;F.value=l;const{tag:b,remote:y}=e;if($(l),b&&!y){if(!l){C.value=Y;return}const{onCreate:p}=e,g=p?p(l):{[e.labelField]:l,[e.valueField]:l},{valueField:m,labelField:L}=e;A.value.some(J=>J[m]===g[m]||J[L]===g[L])||R.value.some(J=>J[m]===g[m]||J[L]===g[L])?C.value=Y:C.value=[g]}}function N(n){n.stopPropagation();const{multiple:l}=e;!l&&e.filterable&&H(),o(),l?K([],[]):K(null,null)}function je(n){!Ie(n,"action")&&!Ie(n,"empty")&&!Ie(n,"header")&&n.preventDefault()}function We(n){le(n)}function $e(n){var l,b,y,p,g;if(!e.keyboard){n.preventDefault();return}switch(n.key){case" ":if(e.filterable)break;n.preventDefault();case"Enter":if(!(!((l=B.value)===null||l===void 0)&&l.isComposing)){if(D.value){const m=(b=q.value)===null||b===void 0?void 0:b.getPendingTmNode();m?ve(m):e.filterable||(H(),Ee())}else if(ie(),e.tag&&re.value){const m=C.value[0];if(m){const L=m[e.valueField],{value:J}=k;e.multiple&&Array.isArray(J)&&J.includes(L)||V(m)}}}n.preventDefault();break;case"ArrowUp":if(n.preventDefault(),e.loading)return;D.value&&((y=q.value)===null||y===void 0||y.prev());break;case"ArrowDown":if(n.preventDefault(),e.loading)return;D.value?(p=q.value)===null||p===void 0||p.next():ie();break;case"Escape":D.value&&(bt(n),H()),(g=B.value)===null||g===void 0||g.focus();break}}function Ee(){var n;(n=B.value)===null||n===void 0||n.focus()}function Ne(){var n;(n=B.value)===null||n===void 0||n.focusInput()}function Ke(){var n;D.value&&((n=G.value)===null||n===void 0||n.syncPosition())}me(),Fe(j(e,"options"),me);const He={focus:()=>{var n;(n=B.value)===null||n===void 0||n.focus()},focusInput:()=>{var n;(n=B.value)===null||n===void 0||n.focusInput()},blur:()=>{var n;(n=B.value)===null||n===void 0||n.blur()},blurInput:()=>{var n;(n=B.value)===null||n===void 0||n.blurInput()}},Ae=P(()=>{const{self:{menuBoxShadow:n}}=v.value;return{"--n-menu-box-shadow":n}}),se=f?nn("select",void 0,Ae,e):void 0;return Object.assign(Object.assign({},He),{mergedStatus:pe,mergedClsPrefix:r,mergedBordered:s,namespace:c,treeMate:T,isMounted:st(),triggerRef:B,menuRef:q,pattern:F,uncontrolledShow:z,mergedShow:D,adjustedTo:Qe(e),uncontrolledValue:h,mergedValue:k,followerRef:G,localizedPlaceholder:ue,selectedOption:ce,selectedOptions:Q,mergedSize:Se,mergedDisabled:oe,focused:E,activeWithoutMenuOpen:re,inlineThemeDisabled:f,onTriggerInputFocus:Re,onTriggerInputBlur:Te,handleTriggerOrMenuResize:Ke,handleMenuFocus:he,handleMenuBlur:ke,handleMenuTabOut:ze,handleTriggerClick:Me,handleToggle:ve,handleDeleteOption:V,handlePatternInput:u,handleClear:N,handleTriggerBlur:Pe,handleTriggerFocus:fe,handleKeydown:$e,handleMenuAfterLeave:ye,handleMenuClickOutside:_e,handleMenuScroll:We,handleMenuKeydown:$e,handleMenuMousedown:je,mergedTheme:v,cssVars:f?void 0:Ae,themeClass:se?.themeClass,onRender:se?.onRender})},render(){return i("div",{class:`${this.mergedClsPrefix}-select`},i(dt,null,{default:()=>[i(ut,null,{default:()=>i(Rt,{ref:"triggerRef",inlineThemeDisabled:this.inlineThemeDisabled,status:this.mergedStatus,inputProps:this.inputProps,clsPrefix:this.mergedClsPrefix,showArrow:this.showArrow,maxTagCount:this.maxTagCount,ellipsisTagPopoverProps:this.ellipsisTagPopoverProps,bordered:this.mergedBordered,active:this.activeWithoutMenuOpen||this.mergedShow,pattern:this.pattern,placeholder:this.localizedPlaceholder,selectedOption:this.selectedOption,selectedOptions:this.selectedOptions,multiple:this.multiple,renderTag:this.renderTag,renderLabel:this.renderLabel,filterable:this.filterable,clearable:this.clearable,disabled:this.mergedDisabled,size:this.mergedSize,theme:this.mergedTheme.peers.InternalSelection,labelField:this.labelField,valueField:this.valueField,themeOverrides:this.mergedTheme.peerOverrides.InternalSelection,loading:this.loading,focused:this.focused,onClick:this.handleTriggerClick,onDeleteOption:this.handleDeleteOption,onPatternInput:this.handlePatternInput,onClear:this.handleClear,onBlur:this.handleTriggerBlur,onFocus:this.handleTriggerFocus,onKeydown:this.handleKeydown,onPatternBlur:this.onTriggerInputBlur,onPatternFocus:this.onTriggerInputFocus,onResize:this.handleTriggerOrMenuResize,ignoreComposition:this.ignoreComposition},{arrow:()=>{var e,r;return[(r=(e=this.$slots).arrow)===null||r===void 0?void 0:r.call(e)]}})}),i(ct,{ref:"followerRef",show:this.mergedShow,to:this.adjustedTo,teleportDisabled:this.adjustedTo===Qe.tdkey,containerClass:this.namespace,width:this.consistentMenuWidth?"target":void 0,minWidth:"target",placement:this.placement},{default:()=>i(vn,{name:"fade-in-scale-up-transition",appear:this.isMounted,onAfterLeave:this.handleMenuAfterLeave},{default:()=>{var e,r,s;return this.mergedShow||this.displayDirective==="show"?((e=this.onRender)===null||e===void 0||e.call(this),ft(i(Ot,Object.assign({},this.menuProps,{ref:"menuRef",onResize:this.handleTriggerOrMenuResize,inlineThemeDisabled:this.inlineThemeDisabled,virtualScroll:this.consistentMenuWidth&&this.virtualScroll,class:[`${this.mergedClsPrefix}-select-menu`,this.themeClass,(r=this.menuProps)===null||r===void 0?void 0:r.class],clsPrefix:this.mergedClsPrefix,focusable:!0,labelField:this.labelField,valueField:this.valueField,autoPending:!0,nodeProps:this.nodeProps,theme:this.mergedTheme.peers.InternalSelectMenu,themeOverrides:this.mergedTheme.peerOverrides.InternalSelectMenu,treeMate:this.treeMate,multiple:this.multiple,size:"medium",renderOption:this.renderOption,renderLabel:this.renderLabel,value:this.mergedValue,style:[(s=this.menuProps)===null||s===void 0?void 0:s.style,this.cssVars],onToggle:this.handleToggle,onScroll:this.handleMenuScroll,onFocus:this.handleMenuFocus,onBlur:this.handleMenuBlur,onKeydown:this.handleMenuKeydown,onTabOut:this.handleMenuTabOut,onMousedown:this.handleMenuMousedown,show:this.mergedShow,showCheckmark:this.showCheckmark,resetMenuOnOptionsChange:this.resetMenuOnOptionsChange}),{empty:()=>{var c,f;return[(f=(c=this.$slots).empty)===null||f===void 0?void 0:f.call(c)]},header:()=>{var c,f;return[(f=(c=this.$slots).header)===null||f===void 0?void 0:f.call(c)]},action:()=>{var c,f;return[(f=(c=this.$slots).action)===null||f===void 0?void 0:f.call(c)]}}),this.displayDirective==="show"?[[ht,this.mergedShow],[sn,this.handleMenuClickOutside,void 0,{capture:!0}]]:[[sn,this.handleMenuClickOutside,void 0,{capture:!0}]])):null}})})]}))}});export{xt as F,Ot as N,$t as _,Rt as a,yt as b,Tt as c,Ge as m,mn as u};
