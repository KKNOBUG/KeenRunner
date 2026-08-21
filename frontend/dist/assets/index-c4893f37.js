import{_ as G,f as _,B as y,o as m,q as A,m as d,w as o,l as t,k as g,n as s,z as W,x as i,a1 as C,ab as z,F as Y,v as J,t as K,y as E,h as X,a2 as Q,C as Z,a9 as ee,aa as te}from"./index-6352ab0f.js";import{N as T,S as ae}from"./StepAssertPanel-548e767a.js";import{u as se,c as ne,b as D,a as re,h as oe,n as de,A as b}from"./useStepEditorForm-ab2e2f99.js";import{_ as ie,a as le}from"./FormItem-bc1e76ea.js";import{_ as ue}from"./Input-6aba4075.js";import{a as N,_ as h}from"./Tabs-046d4c0a.js";import{N as ce}from"./DataTable-92d99789.js";import{N as _e}from"./Empty-7bd5d2d8.js";import"./TheIcon-e494ce78.js";import"./Select-b78cb528.js";import"./Space-33304a0a.js";import"./Add-362a65a9.js";import"./Checkbox-75192690.js";import"./RadioGroup-ea70a3b4.js";import"./download-953ccaa2.js";const u=p=>(ee("data-v-17d87439"),p=p(),te(),p),me={class:"code-container"},pe={class:"card-header-row"},fe=u(()=>t("div",{class:"panel-title"},"Python 代码",-1)),ge={class:"card-header-actions"},he={class:"top-bar"},ve=u(()=>t("div",{class:"python-logo","aria-hidden":"true"},[t("svg",{viewBox:"0 0 128 128",width:"28",height:"28"},[t("linearGradient",{id:"python-gradient-a",gradientUnits:"userSpaceOnUse",x1:"70.252",y1:"1237.476",x2:"170.659",y2:"1151.089",gradientTransform:"matrix(.563 0 0 -.568 -29.215 707.817)"},[t("stop",{offset:"0","stop-color":"#5A9FD4"}),t("stop",{offset:"1","stop-color":"#306998"})]),t("linearGradient",{id:"python-gradient-b",gradientUnits:"userSpaceOnUse",x1:"209.474",y1:"1098.811",x2:"173.62",y2:"1149.537",gradientTransform:"matrix(.563 0 0 -.568 -29.215 707.817)"},[t("stop",{offset:"0","stop-color":"#FFD43B"}),t("stop",{offset:"1","stop-color":"#FFE873"})]),t("path",{fill:"url(#python-gradient-a)",d:"M63.391 1.988c-4.222.02-8.252.379-11.8 1.007-10.45 1.846-12.346 5.71-12.346 12.837v10.411h24.693v3.137H29.977c-7.176 0-13.46 4.313-15.426 12.521-2.268 9.405-2.368 15.275 0 25.096 1.755 7.311 5.947 12.521 13.124 12.521h8.491V67.234c0-8.151 7.051-15.34 15.426-15.34h24.665c6.866 0 12.346-5.654 12.346-12.548V15.833c0-6.693-5.646-11.72-12.346-12.837-4.244-.706-8.645-1.027-12.866-1.008zM50.037 9.557c2.55 0 4.634 2.117 4.634 4.721 0 2.593-2.083 4.69-4.634 4.69-2.56 0-4.633-2.097-4.633-4.69-.001-2.604 2.073-4.721 4.633-4.721z",transform:"translate(0 10.26)"}),t("path",{fill:"url(#python-gradient-b)",d:"M91.682 28.38v10.966c0 8.5-7.208 15.655-15.426 15.655H51.591c-6.756 0-12.346 5.783-12.346 12.549v23.515c0 6.691 5.818 10.628 12.346 12.547 7.816 2.297 15.312 2.713 24.665 0 6.845-1.522 12.346-5.75 12.346-12.547v-9.412H63.938v-3.138h37.012c7.176 0 9.852-5.005 12.348-12.519 2.578-7.735 2.467-15.174 0-25.096-1.774-7.145-5.161-12.521-12.348-12.521H91.682zm28.11 88.33c-2.561 0-4.634 2.097-4.634 4.692 0 2.602 2.074 4.719 4.634 4.719 2.55 0 4.633-2.117 4.633-4.719 0-2.595-2.083-4.692-4.633-4.692z",transform:"translate(0 10.26)"})])],-1)),ye=u(()=>t("div",{class:"hint-box step-editor-hint"},[t("div",{class:"hint-title"},"使用说明"),t("div",{class:"hint-content"},[t("p",null,[i("• 脚本以函数形式作为执行入口，"),t("code",null,"必须符合PEP8编码规范"),i("，声明格式："),t("code",null,"def func() -> dict | list: ...")]),t("p",null,[i("• 脚本返回值支持 "),t("code",null,"Dict[str, Any]"),i(" 或 "),t("code",null,"List[Dict]"),i("：字典时各键写入会话变量池；列表时整体写入变量 "),t("code",null,"result"),i("，方便后续步骤使用")]),t("p",null,[i("• 脚本支持使用 "),t("code",null,"${函数名称}"),i(" 格式占位符调用系统内置函数，使用 "),t("code",null,"${变量名称}"),i(" 格式占位符引用上下文变量")]),t("p",null,[i("• 脚本支持针对执行结果进行断言校验，可"),t("code",null,"从会话变量池读取目标变量，与预设预期值完成各类型比较核验")])])],-1)),be={class:"code-editor-row"},$e={class:"code-snippets-panel"},xe=u(()=>t("div",{class:"code-snippets-title"},"代码片段",-1)),we={class:"code-snippets-list"},ke=["disabled","onClick"],Se=u(()=>t("span",null,"断言",-1)),Ae=u(()=>t("div",{class:"panel-title"},"Response",-1)),Ce=u(()=>t("span",null,"断言",-1)),ze=`import random


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
`,Ee={__name:"index",props:{config:{type:Object,default:()=>({})},step:{type:Object,default:()=>({})},readonly:{type:Boolean,default:!1}},emits:["update:config"],setup(p,{emit:B}){const l=p,O=B,F=(e,a,r)=>{const S=e.assert_validators??a?.assert_validators;return{step_name:e.step_name!==void 0?e.step_name:r||a?.step_name||"",code:e.code!==void 0?e.code:e.script!==void 0?e.script:a?.code||"",assert_validators:oe(de(S),b)}},{form:n}=se({props:l,emit:O,defaults:()=>({step_name:"",code:"",assert_validators:{}}),hydrate:e=>F(e.config||{},e.step?.original,e.step?.name),buildConfig:e=>({step_name:e.step_name||"",code:e.code||"",assert_validators:D(e.assert_validators,b)}),watchFields:e=>[e.step_name,e.code,e.assert_validators]}),L=_(()=>ne(n.assert_validators));function $(){return D(n.assert_validators,b)}const V={theme:"vs-dark",language:"python",fontSize:12,tabSize:4,automaticLayout:!0,minimap:{enabled:!0},lineNumbers:"on",scrollBeyondLastLine:!1,folding:!0},P=_(()=>({...V,readOnly:l.readonly})),j=[{label:"@插入UUID",content:"uuid_str = '${generate_uuid()}'"},{label:"@插入时间戳",content:"timestamp = '${generate_timestamp()}'"},{label:"示例代码",content:ze}];function R(e){return(e?.label||"").startsWith("@")}function U(e){if(l.readonly||!e?.content)return;const a=e.content;if(R(e)&&f.value?.insertAtCursor){f.value.insertAtCursor(a),n.code=f.value.getValue?.()??n.code;return}if(e.label==="示例代码"){n.code=a,f.value?.setValue?.(a);return}n.code=n.code?.trim()?`${n.code}
${a}`:a}const M={theme:"vs-dark",language:"json",fontSize:12,tabSize:2,automaticLayout:!0,minimap:{enabled:!0},lineNumbers:"on",wordWrap:"off",scrollBeyondLastLine:!1,folding:!0,readOnly:!0},f=y(null),v=y(!1),c=y(null),x=_(()=>{const e=c.value;return e?typeof e=="object"&&e.result!==void 0?e.result??{}:e:{}}),w=_(()=>{const e=c.value;return e?typeof e=="object"&&Array.isArray(e.assert_validators)?e.assert_validators:[]:[]}),k=_(()=>w.value.length),H=_(()=>{try{return JSON.stringify(x.value,null,2)}catch{return String(x.value)}}),I=[{title:"断言名称",key:"name",width:120,ellipsis:{tooltip:!0}},{title:"断言对象",key:"source",width:120,render:e=>({变量池:"变量池",session_variables:"变量池"})[e.source]||e.source},{title:"断言路径",key:"expr",width:130,ellipsis:{tooltip:!0}},{title:"结果值",key:"actual_value",width:150,ellipsis:{tooltip:!0},render:e=>e.actual_value===null||e.actual_value===void 0?"-":String(e.actual_value)},{title:"断言方式",key:"operation",width:100},{title:"期望值",key:"except_value",width:120,ellipsis:{tooltip:!0},render:e=>e.except_value===null||e.except_value===void 0?"-":String(e.except_value)},{title:"断言结果",key:"success",width:100,render:e=>X(Q,{type:e.success?"success":"error",round:!0,size:"small"},{default:()=>e.success?"pass":"fail"})},{title:"错误信息",key:"error",ellipsis:{tooltip:!0},render:e=>e.error||"-"}],q=async()=>{if(!n.code||!n.code.trim()){window.$message?.warning?.("请输入要调试的Python代码");return}const e=re($());if(!e.valid){window.$message?.error?.(e.message);return}v.value=!0,c.value=null;try{const a={step_name:n.step_name||"代码请求(Python)",code:n.code,request_args_type:"raw",defined_variables:[],session_variables:[],assert_validators:$()},r=await Z.pythonCodeDebugging(a);r.code==="000000"&&r.data?(c.value=r.data,window.$message?.success?.(r.message||"代码调试成功")):(c.value=r.data,window.$message?.error?.(r.message||"代码调试失败"))}catch(a){console.error("调试请求异常:",a),window.$message?.error?.(a.message||"代码调试异常")}finally{v.value=!1}};return(e,a)=>(m(),A("div",me,[d(s(E),{bordered:!1,class:"step-editor-card"},{header:o(()=>[t("div",pe,[fe,t("div",ge,[l.readonly?C("",!0):(m(),g(s(W),{key:0,type:"primary",size:"small",loading:v.value,onClick:q},{default:o(()=>[i(" 调试 ")]),_:1},8,["loading"]))])])]),default:o(()=>[t("div",he,[ve,d(s(ie),{class:"step-editor-form code-name-form","label-placement":"left","label-width":"80px",size:"small"},{default:o(()=>[d(s(le),{label:"步骤名称","show-feedback":!1},{default:o(()=>[d(s(ue),{value:s(n).step_name,"onUpdate:value":a[0]||(a[0]=r=>s(n).step_name=r),placeholder:"代码请求(Python)",class:"step-name-input",disabled:l.readonly},null,8,["value","disabled"])]),_:1})]),_:1})]),d(s(N),{type:"line",animated:"",class:"code-tabs"},{default:o(()=>[d(s(h),{name:"code",tab:"代码"},{default:o(()=>[ye,t("div",be,[d(z,{ref_key:"codeEditorRef",ref:f,value:s(n).code,"onUpdate:value":a[1]||(a[1]=r=>s(n).code=r),options:P.value,class:"code-editor code-editor-main",style:{"min-height":"500px",height:"auto"}},null,8,["value","options"]),t("aside",$e,[xe,t("ul",we,[(m(),A(Y,null,J(j,r=>t("li",{key:r.label},[t("button",{type:"button",class:"code-snippet-link",disabled:l.readonly,onClick:S=>U(r)},K(r.label),9,ke)])),64))])])])]),_:1}),d(s(h),{name:"assert_validators",tab:"断言"},{tab:o(()=>[d(s(T),{value:L.value,max:99,"show-zero":""},{default:o(()=>[Se]),_:1},8,["value"])]),default:o(()=>[d(ae,{modelValue:s(n).assert_validators,"onUpdate:modelValue":a[2]||(a[2]=r=>s(n).assert_validators=r),mode:"python",readonly:l.readonly},null,8,["modelValue","readonly"])]),_:1})]),_:1})]),_:1}),c.value?(m(),g(s(E),{key:0,bordered:!1,class:"step-editor-card"},{header:o(()=>[Ae]),default:o(()=>[d(s(N),{type:"line",animated:"",class:"debug-tabs"},{default:o(()=>[d(s(h),{name:"result",tab:"结果"},{default:o(()=>[d(z,{value:H.value,options:M,class:"response-editor",style:{"min-height":"500px",height:"auto"},"read-only":!0},null,8,["value"])]),_:1}),d(s(h),{name:"assert",tab:"断言"},{tab:o(()=>[d(s(T),{value:k.value,max:99,"show-zero":""},{default:o(()=>[Ce]),_:1},8,["value"])]),default:o(()=>[k.value>0?(m(),g(s(ce),{key:0,columns:I,data:w.value,bordered:!1,size:"small"},null,8,["data"])):(m(),g(s(_e),{key:1,description:"暂无断言结果"}))]),_:1})]),_:1})]),_:1})):C("",!0)]))}},qe=G(Ee,[["__scopeId","data-v-17d87439"]]);export{qe as default};
