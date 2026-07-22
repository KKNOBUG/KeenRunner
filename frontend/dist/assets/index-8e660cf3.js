import{_ as Y,U as J,f as _,B as $,a2 as T,ad as K,o as m,q as z,m as d,w as r,l as t,k as g,n as o,z as X,x as l,a0 as E,a8 as N,F as Q,v as Z,t as ee,y as O,h as te,a1 as ae,C as se,a6 as ne,a7 as re}from"./index-e99f5908.js";import{c as oe,N as B,S as de,e as ie,n as le,d as ce,a as ue,k as D}from"./StepAssertPanel-5e3446cd.js";import{_ as _e,a as me}from"./FormItem-c7bbe5bc.js";import{_ as pe}from"./Input-8cc4953e.js";import{a as V,_ as v}from"./Tabs-a05a27f4.js";import{N as fe}from"./DataTable-1ca1d0c1.js";import{N as ge}from"./Empty-7a4a7b1d.js";import"./TheIcon-cc5e100d.js";import"./autotestAssertionOperation-bc4bc93b.js";import"./Space-6626f5d9.js";import"./Select-4c5df018.js";import"./Add-c57395e4.js";import"./Checkbox-95fb3bb0.js";import"./RadioGroup-3957a649.js";import"./download-953ccaa2.js";const c=p=>(ne("data-v-eb05a651"),p=p(),re(),p),ve={class:"code-container"},he={class:"card-header-row"},ye=c(()=>t("div",{class:"panel-title"},"Python 代码",-1)),be={class:"card-header-actions"},$e={class:"top-bar"},xe=c(()=>t("div",{class:"python-logo","aria-hidden":"true"},[t("svg",{viewBox:"0 0 128 128",width:"28",height:"28"},[t("linearGradient",{id:"python-gradient-a",gradientUnits:"userSpaceOnUse",x1:"70.252",y1:"1237.476",x2:"170.659",y2:"1151.089",gradientTransform:"matrix(.563 0 0 -.568 -29.215 707.817)"},[t("stop",{offset:"0","stop-color":"#5A9FD4"}),t("stop",{offset:"1","stop-color":"#306998"})]),t("linearGradient",{id:"python-gradient-b",gradientUnits:"userSpaceOnUse",x1:"209.474",y1:"1098.811",x2:"173.62",y2:"1149.537",gradientTransform:"matrix(.563 0 0 -.568 -29.215 707.817)"},[t("stop",{offset:"0","stop-color":"#FFD43B"}),t("stop",{offset:"1","stop-color":"#FFE873"})]),t("path",{fill:"url(#python-gradient-a)",d:"M63.391 1.988c-4.222.02-8.252.379-11.8 1.007-10.45 1.846-12.346 5.71-12.346 12.837v10.411h24.693v3.137H29.977c-7.176 0-13.46 4.313-15.426 12.521-2.268 9.405-2.368 15.275 0 25.096 1.755 7.311 5.947 12.521 13.124 12.521h8.491V67.234c0-8.151 7.051-15.34 15.426-15.34h24.665c6.866 0 12.346-5.654 12.346-12.548V15.833c0-6.693-5.646-11.72-12.346-12.837-4.244-.706-8.645-1.027-12.866-1.008zM50.037 9.557c2.55 0 4.634 2.117 4.634 4.721 0 2.593-2.083 4.69-4.634 4.69-2.56 0-4.633-2.097-4.633-4.69-.001-2.604 2.073-4.721 4.633-4.721z",transform:"translate(0 10.26)"}),t("path",{fill:"url(#python-gradient-b)",d:"M91.682 28.38v10.966c0 8.5-7.208 15.655-15.426 15.655H51.591c-6.756 0-12.346 5.783-12.346 12.549v23.515c0 6.691 5.818 10.628 12.346 12.547 7.816 2.297 15.312 2.713 24.665 0 6.845-1.522 12.346-5.75 12.346-12.547v-9.412H63.938v-3.138h37.012c7.176 0 9.852-5.005 12.348-12.519 2.578-7.735 2.467-15.174 0-25.096-1.774-7.145-5.161-12.521-12.348-12.521H91.682zm28.11 88.33c-2.561 0-4.634 2.097-4.634 4.692 0 2.602 2.074 4.719 4.634 4.719 2.55 0 4.633-2.117 4.633-4.719 0-2.595-2.083-4.692-4.633-4.692z",transform:"translate(0 10.26)"})])],-1)),ke=c(()=>t("div",{class:"hint-box step-editor-hint"},[t("div",{class:"hint-title"},"使用说明"),t("div",{class:"hint-content"},[t("p",null,[l("• 脚本以函数形式作为执行入口，"),t("code",null,"必须符合PEP8编码规范"),l("，声明格式："),t("code",null,"def func() -> dict: ...")]),t("p",null,[l("• 脚本返回值固定要求为字典类型："),t("code",null,"Dict[str, Any]"),l("，运行结果同步存入会话变量池中，方便后续步骤使用")]),t("p",null,[l("• 脚本支持使用 "),t("code",null,"${函数名称}"),l(" 格式占位符调用系统内置函数，使用 "),t("code",null,"${变量名称}"),l(" 格式占位符引用上下文变量")]),t("p",null,[l("• 脚本支持针对执行结果进行断言校验，可"),t("code",null,"从会话变量池读取目标变量，与预设预期值完成各类型比较核验")])])],-1)),we={class:"code-editor-row"},Se={class:"code-snippets-panel"},Ae=c(()=>t("div",{class:"code-snippets-title"},"代码片段",-1)),Ce={class:"code-snippets-list"},Te=["disabled","onClick"],ze=c(()=>t("span",null,"断言",-1)),Ee=c(()=>t("div",{class:"panel-title"},"Response",-1)),Ne=c(()=>t("span",null,"断言",-1)),Oe=`import random


def generate_test_data() -> dict:
    """
    利用内置函数生成虚拟数据
    :return:
    """
    job = '\${generate_job()}'
    name = '\${generate_name()}'
    phone = '\${generate_phone()}'
    email = '\${generate_email()}'
    address = '\${generate_address()}'
    id_card = '\${generate_ident_card_number()}'
    birthday = f'\${{generate_ident_card_birthday(ident_card_number={id_card})}}'
    gender = f'\${{generate_ident_card_gender(ident_card_number={id_card})}}'
    datetime_str1 = '\${generate_datetime(fmt=11)}'
    datetime_str2 = '\${generate_datetime(fmt=21)}'
    datetime_str3 = '\${generate_datetime(fmt=31)}'
    datetime_str4 = '\${generate_datetime(fmt=41)}'
    datetime_str5 = '\${generate_datetime(fmt=42)}'
    datetime_str6 = '\${generate_datetime(fmt=51)}'
    datetime_str7 = '\${generate_datetime(fmt=52)}'
    random_float = '\${generate_float(min_=100, max_=999, num_3)}'
    random_int1 = '\${generate_random_int(min_=100000, max_=999999)}'
    random_int2 = '\${generate_random_int(min_=100, max_=999)}'
    random_int3 = '\${generate_string(length=10, digit=True)}'
    random_str1 = '\${generate_string(length=10, char=True)}'
    random_str2 = '\${generate_string(length=10, chinese=True)}'
    random_str3 = '\${generate_string(length=20, char=True, chinese=True, digit=True)}'

    # 布尔 & 状态
    is_active = random.choice([True, False])
    status = random.choice(["pending", "success", "failed", "closed"])
    return {
        "id": random_int1,
        "no": random_int2,
        "username": name,
        "password": random_str1,
        "phone": phone,
        "email": email,
        "job": job,
        "address": address,
        "id_card": id_card,
        "birthday": birthday,
        "gender": gender,
        "random_str1": random_str3,
        "random_str2": random_str2,
        "random_int": random_int3,
        "random_float": random_float,
        "datetime_str1": datetime_str1,
        "datetime_str2": datetime_str2,
        "datetime_str3": datetime_str3,
        "datetime_str4": datetime_str4,
        "datetime_str5": datetime_str5,
        "datetime_str6": datetime_str6,
        "datetime_str7": datetime_str7,
        "is_active": is_active,
        "status": status,
    }
`,Be={__name:"index",props:{config:{type:Object,default:()=>({})},step:{type:Object,default:()=>({})},readonly:{type:Boolean,default:!1}},emits:["update:config"],setup(p,{emit:L}){const i=p,F=L,x={step_name:"",code:"",assert_validators:{}},k=(e,s,n)=>{const C=e.assert_validators??s?.assert_validators;return{step_name:e.step_name!==void 0?e.step_name:n||s?.step_name||"",code:e.code!==void 0?e.code:e.script!==void 0?e.script:s?.code||"",assert_validators:ie(le(C),D)}},a=J({...x,...k(i.config,i.step?.original,i.step?.name)}),P=_(()=>oe(a.assert_validators));function h(){return ce(a.assert_validators,D)}const U={theme:"vs-dark",language:"python",fontSize:12,tabSize:4,automaticLayout:!0,minimap:{enabled:!0},lineNumbers:"on",scrollBeyondLastLine:!1,folding:!0},j=_(()=>({...U,readOnly:i.readonly})),R=[{label:"@插入UUID",content:"uuid_str = '${generate_uuid()}'"},{label:"@插入时间戳",content:"timestamp = '${generate_timestamp()}'"},{label:"示例代码",content:Oe}];function M(e){return(e?.label||"").startsWith("@")}function H(e){if(i.readonly||!e?.content)return;const s=e.content;if(M(e)&&f.value?.insertAtCursor){f.value.insertAtCursor(s),a.code=f.value.getValue?.()??a.code;return}if(e.label==="示例代码"){a.code=s,f.value?.setValue?.(s);return}a.code=a.code?.trim()?`${a.code}
${s}`:s}const I={theme:"vs-dark",language:"json",fontSize:12,tabSize:2,automaticLayout:!0,minimap:{enabled:!0},lineNumbers:"on",wordWrap:"off",scrollBeyondLastLine:!1,folding:!0,readOnly:!0},f=$(null),y=$(!1),u=$(null),w=_(()=>{const e=u.value;return e?typeof e=="object"&&e.result!==void 0?e.result||{}:e:{}}),S=_(()=>{const e=u.value;return e?typeof e=="object"&&Array.isArray(e.assert_validators)?e.assert_validators:[]:[]}),A=_(()=>S.value.length),q=_(()=>{try{return JSON.stringify(w.value,null,2)}catch{return String(w.value)}}),G=[{title:"断言名称",key:"name",width:120,ellipsis:{tooltip:!0}},{title:"断言对象",key:"source",width:120,render:e=>({变量池:"变量池",session_variables:"变量池"})[e.source]||e.source},{title:"断言路径",key:"expr",width:130,ellipsis:{tooltip:!0}},{title:"结果值",key:"actual_value",width:150,ellipsis:{tooltip:!0},render:e=>e.actual_value===null||e.actual_value===void 0?"-":String(e.actual_value)},{title:"断言方式",key:"operation",width:100},{title:"期望值",key:"except_value",width:120,ellipsis:{tooltip:!0},render:e=>e.except_value===null||e.except_value===void 0?"-":String(e.except_value)},{title:"断言结果",key:"success",width:100,render:e=>te(ae,{type:e.success?"success":"error",round:!0,size:"small"},{default:()=>e.success?"pass":"fail"})},{title:"错误信息",key:"error",ellipsis:{tooltip:!0},render:e=>e.error||"-"}];let b=!1;T(()=>i.step?.id,()=>{b=!0;const e=k(i.config||{},i.step?.original,i.step?.name);Object.assign(a,x,e),K(()=>{b=!1})},{immediate:!0}),T(()=>[a.step_name,a.code,a.assert_validators],()=>{b||i.readonly||F("update:config",{step_name:a.step_name||"",code:a.code||"",assert_validators:h()})},{deep:!0});const W=async()=>{if(!a.code||!a.code.trim()){window.$message?.warning?.("请输入要调试的Python代码");return}const e=ue(h());if(!e.valid){window.$message?.error?.(e.message);return}y.value=!0,u.value=null;try{const s={step_name:a.step_name||"代码请求(Python)",code:a.code,request_args_type:"raw",defined_variables:[],session_variables:[],assert_validators:h()},n=await se.pythonCodeDebugging(s);n.code==="000000"&&n.data?(u.value=n.data,window.$message?.success?.(n.message||"代码调试成功")):(u.value=n.data,window.$message?.error?.(n.message||"代码调试失败"))}catch(s){console.error("调试请求异常:",s),window.$message?.error?.(s.message||"代码调试异常")}finally{y.value=!1}};return(e,s)=>(m(),z("div",ve,[d(o(O),{bordered:!1,class:"step-editor-card"},{header:r(()=>[t("div",he,[ye,t("div",be,[i.readonly?E("",!0):(m(),g(o(X),{key:0,type:"primary",size:"small",loading:y.value,onClick:W},{default:r(()=>[l(" 调试 ")]),_:1},8,["loading"]))])])]),default:r(()=>[t("div",$e,[xe,d(o(_e),{class:"step-editor-form code-name-form","label-placement":"left","label-width":"80px",size:"small"},{default:r(()=>[d(o(me),{label:"步骤名称","show-feedback":!1},{default:r(()=>[d(o(pe),{value:a.step_name,"onUpdate:value":s[0]||(s[0]=n=>a.step_name=n),placeholder:"代码请求(Python)",class:"step-name-input",disabled:i.readonly},null,8,["value","disabled"])]),_:1})]),_:1})]),d(o(V),{type:"line",animated:"",class:"code-tabs"},{default:r(()=>[d(o(v),{name:"code",tab:"代码"},{default:r(()=>[ke,t("div",we,[d(N,{ref_key:"codeEditorRef",ref:f,value:a.code,"onUpdate:value":s[1]||(s[1]=n=>a.code=n),options:j.value,class:"code-editor code-editor-main",style:{"min-height":"500px",height:"auto"}},null,8,["value","options"]),t("aside",Se,[Ae,t("ul",Ce,[(m(),z(Q,null,Z(R,n=>t("li",{key:n.label},[t("button",{type:"button",class:"code-snippet-link",disabled:i.readonly,onClick:C=>H(n)},ee(n.label),9,Te)])),64))])])])]),_:1}),d(o(v),{name:"assert_validators",tab:"断言"},{tab:r(()=>[d(o(B),{value:P.value,max:99,"show-zero":""},{default:r(()=>[ze]),_:1},8,["value"])]),default:r(()=>[d(de,{modelValue:a.assert_validators,"onUpdate:modelValue":s[2]||(s[2]=n=>a.assert_validators=n),mode:"python",readonly:i.readonly},null,8,["modelValue","readonly"])]),_:1})]),_:1})]),_:1}),u.value?(m(),g(o(O),{key:0,bordered:!1,class:"step-editor-card"},{header:r(()=>[Ee]),default:r(()=>[d(o(V),{type:"line",animated:"",class:"debug-tabs"},{default:r(()=>[d(o(v),{name:"result",tab:"结果"},{default:r(()=>[d(N,{value:q.value,options:I,class:"response-editor",style:{"min-height":"500px",height:"auto"},"read-only":!0},null,8,["value"])]),_:1}),d(o(v),{name:"assert",tab:"断言"},{tab:r(()=>[d(o(B),{value:A.value,max:99,"show-zero":""},{default:r(()=>[Ne]),_:1},8,["value"])]),default:r(()=>[A.value>0?(m(),g(o(fe),{key:0,columns:G,data:S.value,bordered:!1,size:"small"},null,8,["data"])):(m(),g(o(ge),{key:1,description:"暂无断言结果"}))]),_:1})]),_:1})]),_:1})):E("",!0)]))}},Je=Y(Be,[["__scopeId","data-v-eb05a651"]]);export{Je as default};
