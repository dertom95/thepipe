import re,argparse,os,time
import shutil

from sys import platform
from pathlib import Path
from xml.etree import ElementTree
import subprocess

from tools import BoolValue,NumberValue,FileValue,EnumValue,StringValue, VectorValue

HOST=None
if platform == "linux" or platform == "linux2":
    HOST="linux"
elif platform == "darwin":
    HOST="mac"
elif platform == "win32":
    HOST="win"
else:
    raise AttributeError("Unknown platform: %s"  %  platform)


def xgetrequired(xml,attrib):
    if attrib in xml.attrib:
        return xml.attrib[attrib]
    else:
        raise NameError("required attribute '%s' was not found in:\n%s" %(attrib,ElementTree.tostring(xml)))


def xget(xml,attrib,default_value=None,to_lower=False):
    result=default_value
    if attrib in xml.attrib:
        result=xml.attrib[attrib]
    if result==None:
        return None
    if to_lower:
        return result.lower()
    else:
        return result

def xget_b(xml,attrib,default_value):
    if attrib in xml.attrib:
        return xml.attrib[attrib].lower()=="true"
    else:
        return default_value

       
def xget_parameters(xml):
    params={}
    for param in xml.iter("param"):
        id = xgetrequired(param,"id")
        output = xget(param,"output","")
        default_value = xget(param,"default","")
        required = xget_b(param,"required",False)
        type_signature = xget(param,"type","string",True)
        description = xget(param,"description","")
        tool_type=create_type(type_signature,default_value,required)
        params[id]=(id,output,tool_type,type_signature,description)
    return params

def create_type(type_signature,default_value,required):
    if type_signature=="bool":
        return BoolValue(default_value,required)
    elif type_signature=="string":
        return StringValue(default_value,required)
    elif type_signature.startswith("vec"):
        m=re.match(r"vec\[(.+?)\]",type_signature)
        if not m:
            raise AttributeError("Unknown vectortype:%s" % type_signature)
        dim = int(m.group(1))
        return VectorValue(dim,default_value,required)
    elif type_signature.startswith("number"):
        if type_signature=="number":
            return NumberValue(0,0,float("inf"),required)
        
        m = re.match(r"number\[([0-9.]+?)-([0-9.]+?)\]",type_signature)
        
        if m:
            from_value = m.group(1)
            to_value   = m.group(2)
            return NumberValue(default_value,from_value,to_value,required)
        else:
            raise AttributeError("Unknown number-signature:%s" % type_signature)
    elif type_signature=="file":
        return FileValue(required)
    elif type_signature.startswith("enum"):
        result_type = EnumValue(required)
        enum_pattern=r"enum\[(([\w\d]+?)(,|\]))"
        m = re.search(enum_pattern,type_signature)
        while m:
            all=m.group(1)
            enum_value=m.group(2)
            result_type.add_enum_value(enum_value)

            type_signature=type_signature.replace(all,"")
            m = re.search(enum_pattern,type_signature)
        return result_type
    else:
        raise AttributeError("Unknown type:%s",type_signature)

class Converter:
    CONVERTERS = {}

    def __init__(self,xml):
        self.prefix = xgetrequired(xml,"prefix")
        self.name   = xgetrequired(xml,"name")
        self.target = xget(xml,"target","all")
        
        cmd = xml.find("command")
        if cmd is None:
            raise AttributeError("Converter without command-tag!: %s" % ElementTree.tostring(xml))

        self.tool_id = xgetrequired(cmd,"toolid")
        self.tool_args = xgetrequired(cmd,"arguments")
        self.tool_out_ext = xget(cmd,"extension",None)

        self.params = xget_parameters(xml)
    
    def qualified_name(self):
        return "%s-%s" % (self.prefix,self.name)

    def add(converter):
        qn = converter.qualified_name()
        if qn in Converter.CONVERTERS:
            raise KeyError("There is already a converter with the qn:%s" % qn)

        Converter.CONVERTERS[qn]=converter

    def add_from_xml(xml):
        converter = Converter(xml)
        Converter.add(converter)

    def reset_params(self):
        for key in self.params:
            id,output,tool_type,type_signature,description=self.params[key]
            tool_type.reset()

    def execute(self,temp_folder,in_file,xml_data,file_history,executions):
        self.reset_params()
        id,output,tool_type,type_signature,description=self.params["in"]
        tool_type.set(in_file)

        filename, file_extension = os.path.splitext(file_history[0])
        file_extension=file_extension[1:]
        filename_without_folder = os.path.basename(filename)
        if self.tool_out_ext:
            file_extension=self.tool_out_ext

        out_file = "%s%s-%s-%s.%s" %(temp_folder,self.qualified_name(),filename_without_folder,time.time(),file_extension)
        
        id,output,tool_type,type_signature,description=self.params["out"]
        tool_type.set(out_file)

        for attrib in xml_data.attrib:
            if attrib in self.params:
                value = xml_data.attrib[attrib]
                id,output,tool_type,type_signature,description=self.params[attrib]
                tool_type.set(value)
        
        tool = Tool.get(self.tool_id)

        arguments = self.tool_args

        for p in self.params:
            (id,output,tool_type,type_signature,description) = self.params[p]
            if not tool_type.value_set():
                continue
            
            direct_tag = r"@[%s]"%id
            param_output = tool_type.output(output)
            if direct_tag in arguments:
                arguments=arguments.replace(direct_tag,param_output)
            else:
                arguments=arguments.replace("@@","%s @@" % param_output)

        arguments=arguments.replace("@@","")

        # let the Tool do the execution(!)
        retcode,execution_call = tool.execute(arguments)
        executions.append(execution_call)

        file_history.append(out_file)


        return retcode,out_file
        
        

    
    def get(qn):
        if qn not in Converter.CONVERTERS:
            return None
            #raise KeyError("there is no converter with the qn:%s" % qn)

        return Converter.CONVERTERS[qn]

    def has(qn):
        return qn in Converter.CONVERTERS

class Tool:
    TOOLS={}

    def __init__(self,xml):
        print(ElementTree.tostring(xml))
        self.xml=xml
        self.tool_type=xgetrequired(xml,"type")
        self.tool_id=xgetrequired(xml,"id")
        self.version=xget(xml,"version","unknown")
        self.is_default=xget_b(xml,"default",False)
        self.command=None
        for cmd in xml.iter("command"):
            host = xgetrequired(cmd,"host")
            if host!=HOST:
                # ignore tools for other HOSTs
                continue

            if self.tool_type=="cli":
                file = xgetrequired(cmd,"file")
                self.command=file.replace("@",os.getcwd())
            else:
                raise AttributeError("Unknown ToolType:%s" % self.tool_type)

    def qualified_name(self):
        return "%s.%s" % (self.tool_id,self.version)

    def add(tool):
        tid=tool.tool_id

        if  tid not in Tool.TOOLS:
            Tool.TOOLS[tid]={}
        tool_bag = Tool.TOOLS[tid]
        if tool.version in tool_bag:
            raise NameError("[%s] There was already a version %s registered!" % ( tid,tool.version ))

        tool_bag[tool.version]=tool
        if "default" not in tool_bag or tool.is_default:
            tool_bag["default"]=tool

    def get(tool_id,version="default"):
        # TODO: handle versions
        if tool_id not in Tool.TOOLS:
            raise KeyError("Unknown tool with tool_id: %s" % tool_id)
        
        return Tool.TOOLS[tool_id][version]

    # def get_command(self):
    #     if HOST not in self.commands:
    #         raise KeyError("[Tool:%s] Not command for OS[%s]" % (self.tool_id,HOST))
    #     return self.commands[HOST]

    def add_from_xml(xml):
        tool = Tool(xml)
        Tool.add(tool)

    def execute(self,arguments):
        execution_command = "%s %s" % (self.command,arguments)
        retcode = os.system(execution_command)

        return retcode,execution_command


class FileRepository:
    def __init__(self,folder):
        self.folder=folder
    
    def get_file(self,input):
        filename="%s/%s" % (self.folder,input)
        if not os.path.exists(filename):
            raise AttributeError("FileRepo[%s]. Could not locate file:%s" % (self.folder,input))

        return os.path.abspath(filename)

    def write_file(self,input,output_in_repo):
        output_filename="%s/%s" % (self.folder,output_in_repo)
        directory = os.path.dirname(output_filename)
        try:
            os.makedirs(directory)
        except:
            pass
        shutil.copyfile(input,output_filename)

class InputFile:
    def __init__(self,relative_part,repo="cwd"):
        self.repo=repo
        self.relative_part=relative_part

    def retrieve(self,context):
        repo = context.get_repository(self.repo)
        file = repo.get_file(self.relative_part)
        return file


class Context:
    def __init__(self,args):
        self.input_files = args.input
        self.keep_intermediate = args.keep_intermediate_files
        self.repositories={}

    def add_repository_from_xml(self,xml):
        name = xgetrequired(xml,"name")

        if name in self.repositories:
            raise AttributeError("Repositiory with name:%s already present!" % name)

        if xml.tag=="file-repository":
            folder = xgetrequired(xml,"folder")
            file_repo = FileRepository(folder)
            self.repositories[name]=file_repo
    
    def get_repository(self,repo_name):
        return self.repositories[repo_name]

    def retrieve_input(self,xml_input):
        tag = xml_input.tag.lower()
        if tag=="file":
            filename = xgetrequired(xml_input,"filename")
            repo_name = xget(xml_input,"repository","cwd")
            input_file = InputFile(filename,repo_name).retrieve(self)
            return (repo_name,input_file)
        else:
            raise AttributeError("Unknown input-type:%s" % tag)

    def resolve_variables_in_string(self,string_data,shared_locals):
        pattern = r"@\[(.+?)\]"
        m = re.search(pattern,string_data)
        while m:
            all = m.group(0)
            var_name = m.group(1)
            if var_name in shared_locals:
                data = shared_locals[var_name]
                string_data=string_data.replace(all,str(data))
            m = re.search(pattern,string_data)

        if "@[" in string_data:
            raise AttributeError("Could not resolve all variables:%s" % string_data)

        return string_data

    def resolve_attribute_variables(self,xml,shared_locals):
        for attrib in xml.attrib:
            resolved = self.resolve_variables_in_string(xml.attrib[attrib],shared_locals)
            xml.attrib[attrib]=resolved

    def execute_pipeline(self,xml_pipeline):
        shared_globals=dict()
        shared_locals=dict()

        execution_calls=[]

        target = xget(xml_pipeline,"target","all")
        pipeline_name = xgetrequired(xml_pipeline,"pl-name")

        pipeline_folder = "temp/%s%s/" % (pipeline_name,time.time())
        try:
            os.makedirs(pipeline_folder)
        except:
            pass

        shared_locals["target"]=target

        init=xml_pipeline.find("init")
        if init is None:
            raise AttributeError("Pipeline without init:\n%s" % ElementTree.tostring(xml_pipeline))

        for ev in init.iter("eval"):
            ev_str = ev.text
            exec(ev_str,shared_globals,shared_locals)
            execution_calls.append("eval start:\n%s\neval end:------" % ev_str)

        xml_input=init.find("input")
        if xml_input is None:
            raise AttributeError("Pipeline.Init without <input/>\n%s" % ElementTree.tostring(xml_pipeline))
        
        for _input in xml_input:
            repo_name,input_filename = self.retrieve_input(_input)
            shared_locals["repo_name"]=repo_name
            
            file_history=[input_filename]

            shared_locals["init-full-filename"]=input_filename
            in_file = os.path.basename(input_filename)
            filename_wo_ext, file_extension = os.path.splitext(in_file)
            file_extension=file_extension[1:]
            shared_locals["init-filename"]=in_file
            shared_locals["init-file-wo-ext"]=filename_wo_ext
            shared_locals["init-file-ext"]=file_extension

            # execute pipeline for every input
            for command in xml_pipeline:
                shared_locals["full-filename"]=input_filename
                in_file = os.path.basename(input_filename)
                filename_wo_ext, file_extension = os.path.splitext(in_file)
                file_extension=file_extension[1:]
                shared_locals["filename"]=in_file
                shared_locals["file-wo-ext"]=filename_wo_ext
                shared_locals["file-ext"]=file_extension

                tag = command.tag.lower()
                if tag=="init":
                    continue

                ## CONVERTER ##
                converter = Converter.get(tag)
                if converter:
                    self.resolve_attribute_variables(command,shared_locals)
                    result,input_filename = converter.execute(pipeline_folder,input_filename,command,file_history,execution_calls)
                ## PYTHON-EVAL ##
                elif tag=="eval":
                    ev_str = command.text
                    exec(ev_str,shared_globals,shared_locals)
                    execution_calls.append("eval start:\n%s\neval end:------" % ev_str)
                ## OUTPUT / COPY ##
                elif tag=="output":
                    repo_name=xget(command,"repository","cwd")
                    filename=xgetrequired(command,"filename")
                    
                    filename=self.resolve_variables_in_string(filename,shared_locals)

                    repo = self.get_repository(repo_name)
                    repo.write_file(input_filename,filename)
                    
                    execution_calls.append("output:%s => [%s]:%s" % (input_filename,repo_name,filename))

        execution_file = open("%s%s-exe-list.%s.txt" % (pipeline_folder,pipeline_name,time.time()),"w")
        execution_text = "\n".join(execution_calls)        
        execution_file.write(execution_text)
        execution_file.close()

        if not self.keep_intermediate:
            shutil.rmtree(pipeline_folder)
                   



    def execute_file(self,filename):
        xml = ElementTree.parse(filename).getroot()
        repos = xml.find("repositories")
        if repos is not None:
            for repo in repos:
                self.add_repository_from_xml(repo)
        self.repositories["cwd"]=FileRepository(os.getcwd())

        for pipeline in xml.iter("pipeline"):
            self.execute_pipeline(pipeline)
                

    def run(self):
        for file in self.input_files:
            self.execute_file(file)



def load_plugins(folder="plugins"):
    xml_files = Path(folder).rglob("*.xml")
    xml_element_tree = None
    for xml_file in xml_files:
        data = ElementTree.parse(xml_file).getroot()
        if xml_element_tree is None:
            xml_element_tree=data
        else:
            xml_element_tree.extend(data)
    return xml_element_tree

def parse_tools(xml_data):
    for tool in xml_data.iter("tool"):
        Tool.add_from_xml(tool)

    for converter in xml_data.iter("converter"):
        Converter.add_from_xml(converter)

def parse_arguments():
    parser = argparse.ArgumentParser(description="thepipeline - universal assets processor")
    parser.add_argument("--input",action="append",help="input xml-files", required=True)
    parser.add_argument("--keep-intermediate-files",type=bool,default=False,help="keep files generated during runtime")
    args = parser.parse_args()

    ctx = Context(args)
    return ctx

def execute_context(ctx):
    pass    

def startup():
    xml = load_plugins()
    parse_tools(xml)

    ctx = parse_arguments()
    ctx.run()

startup()