import re,os

from pkg_resources import add_activation_listener
from xsd_creator import XSDCreator

class InputFile:
    def __init__(self,context,relative_part,repo,target):
        self.context=context
        self.target=target
        self.repo=repo
        self.relative_part=relative_part.replace("%s://"%repo,"")

    def retrieve(self,resolve_glob=False,check_existance=True):
        repo = self.context.get_repository(self.repo)
        if resolve_glob:
            files = repo.get_file(self.relative_part,check_existance,True,True)
            return files
        else:
            file = repo.get_file(self.relative_part)
            return file

class NumberValue:
    def __init__(self,default_value=16,min=0,max=float("inf"),required=False,is_integer=True):
        self.is_integer=is_integer
        self.min=int(min) if is_integer else float(min)
        self.max=int(max) if is_integer else float(max)
        try:
            self.default_value=int(default_value)  if is_integer else float(default_value)
        except:
            self.default_value=0

        self.value=int(self.default_value) if is_integer else float(self.default_value)
        self.required=required
        self.is_set=False

    def put_xsd(self,creator,block,blockname,name):
#        creator.add_attribute(block,name,self.required,"xs:int" if self.is_integer else "xs:float")
        creator.add_attribute(block,name,self.required,"xs:string" if self.is_integer else "xs:float")

    def set(self,value):
        value=int(value) if self.is_integer else float(value)
        if value < self.min:
            value=self.min
        if value > self.max:
            value=self.max
        self.value=value
        self.is_set=True
    
    def get(self):
        return self.value

    def reset(self):
        self.value=self.default_value
        self.is_set=False        

    def value_set(self):
        return self.is_set

    def output(self,template):
        return template.replace("@",str(self.value))        

class VectorValue:
    def __init__(self,dimensions,default_value=None,required=False):
        self.is_set=False
        if default_value:
            self.data=default_value
        else:
            self.data=dimensions*[0]
        self.required=required
        self.dimensions=dimensions
        self.is_set=False

    def put_xsd(self,creator:XSDCreator,block,blockname,name):
        typename="vec%stype"%self.dimensions
        creator.create_enum_type(typename,[",".join(3*["VAL"])])
        creator.add_attribute(block,name,self.required,typename)

    def set(self,value):
        splits = re.split(r"x|,",value)
        self.data=splits
        self.is_set=True

    def value_set(self):
        return self.is_set

    def output(self,template):
        for i in range(self.dimensions):
            template=template.replace("@[%s]"%i,self.data[i])
        template=template.replace("@",str(self.data))
        return template
    
    def reset(self):
        self.data=self.dimensions*[0]        
        self.is_set=False


class FileValue:
    def __init__(self,required=False):
        self.is_set=False
        self.value=None
        self.required=required
        self.from_repo=None

    def set(self,value):
        self.is_set=True
        self.value=value
        #todo: check if file is available!?

    def put_xsd(self,creator,block,blockname,name):
        creator.add_attribute(block,name,self.required)        

    def get(self):
        return self.value

    def reset(self):
        self.value=None
        self.is_set=False        

    def value_set(self):
        return self.is_set

    def escape(self,filename):
        return "'%s'"%filename

    def output(self,template):
        return template.replace("@",self.escape(self.value))

class MultiFileValue:
    def __init__(self,required=False):
        self.is_set=False
        self.value=[]
        self.required=required
        self.data=None

    def set(self,values):
        for val in values:
            self.add_file(val[1])

    def add_file(self,file):
        self.value = self.value or []
        _file=FileValue()
        _file.set(file)
        self.value.append(_file)
        self.is_set=True
    
    def add_files(self,files):
        for val in files:
            self.add_file(val[1])
        
    def get(self):
        return self.value

    def reset(self):
        self.value=None
        self.is_set=False        

    def value_set(self):
        return self.is_set

    # todo: this is messy. do this somewhere else?
    def set_files_from_data(self,ctx,shared_locals):
        result = []
        if self.data and len(self.data)>0:
            filename_file=self.data[0]
            filename_file=ctx.resolve_variables_in_string(filename_file,shared_locals)
            folder = os.path.dirname(filename_file)
            if not os.path.exists(filename_file):
                raise AttributeError("Could not find Multifile-Inputfile: %s" % filename_file)

            with open(filename_file) as f:
                lines = f.readlines()
                for line in lines:
                    line=line.strip()
                    result.append((None,os.path.abspath(line)))
                    self.add_file(os.path.abspath("%s"%(line)))
        return result

    def output(self,template):
        result=""
        for f in self.value:
            result+=f.output("@ ")
        return template.replace("@",result)
    


class StringValue:
    def __init__(self,default_value,required=False):
        self.is_set=False
        self.value=default_value
        self.default_value=default_value
        self.required=required

    def put_xsd(self,creator,block,blockname,name):
        creator.add_attribute(block,name,self.required)

    def set(self,value):
        self.is_set=True
        self.value=value

    def get(self):
        return self.value

    def reset(self):
        self.is_set=False
        self.value=self.default_value
        self.is_set=False        

    def value_set(self):
        return self.is_set

    def output(self,template):
        return template.replace("@",self.value)



class EnumValue:
    def __init__(self,default_value,required=False,strict=False):
        self.is_set=False
        self.value=default_value
        self.required=required
        self.enum_values=[]
        self.default_value=default_value
        self.strict=strict

    def put_xsd(self,creator,block,blockname,name):
        typename="%s_%stype"%(blockname,name)
        creator.create_enum_type(typename,self.enum_values,self.strict)
        creator.add_attribute(block,name,self.required,typename)        

    def add_enum_value(self,value):
        if value not in self.enum_values:
            self.enum_values.append(value)

    def get(self):
        return self.value
    
    def set(self,value):
        self.is_set=True
        if value in self.enum_values or not self.strict:
            self.value=value
        else:
            raise AttributeError("Tried to set invalid enum-value:%s" % value)

    def reset(self):
        self.value=self.default_value
        self.is_set=False        

    def value_set(self):
        return self.is_set

    def output(self,template):
        return template.replace("@",self.value)

class BoolValue:
    def __init__(self,default_value,required=False):
        self.is_set=False
        self.default_value=default_value
        self.required=required
        self.value=default_value
    
    def put_xsd(self,creator:XSDCreator,block,blockname,name):
        creator.create_enum_type("booltype",["true","false"],True)
        creator.add_attribute(block,name,self.required,"booltype")

    def set(self,value):
        self.is_set=True
        self.value=value

    def get(self):
        return self.value

    def reset(self):
        self.value=self.default_value
        self.is_set=False        

    def value_set(self):
        return self.is_set

    def output(self,template):
        splits=template.split("||")
        if self.value:
            if len(splits)>0:
                return splits[0]
        else:
            if len(splits)>1:
                return splits[1]
        return ""            

class CLICommand:
    pattern = "#(.+?)#"
    
    def __init__(self,command):
        self.command=command
        
    def execute(self,data):
        command = self.command
        m = re.search(CLICommand.pattern,command)
        while m:
            grp = m.group(1)
            split=grp.split('|')
                
            if split[0] in data:
                if len(split)==2:
                    command = command.replace(m.group(),split[1])
                else:
                    command = command.replace(m.group(),data[grp])
            else:
                command = command.replace(m.group(),"")                

            m = re.search(CLICommand.pattern,command)

        print(command)
        return_value=os.system(command)



