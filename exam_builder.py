"""
My wife is a teacher and has to build, and maintain, exams over multiple
courses and many semesters. These are straightforward, good old-fashioned
exams: mostly multiple choice questions and maybe some simple short-answer
questions. You would think your basic word processor would be up to this task,
but in fact it's quite a pain: shuffling question and answer order takes a lot
of manual work, and WYSIWYG formatting still sucks. (Especially if, like my
wife, you team teach courses and a single exam is a copy-and-pasted blend of
three different people's unique word processing styles.

So one day I offered to help. After 30 minutes of yelling at Word, I threw my
hands up and said, "Enough! I will fix this with Python, YAML, and Markdown."
Here's the result: you write your exam in a YAML file, run this script on the
file and it produces two PDF files: your exam and an answer key. Optionally,
question order and answer order are shuffled each build. You can use Markdown
within your question and the answers. See the example in the 'examples'
directory.

I know quite a few teachers, so I thought I'd clean this up and put it out
there. It's a simple example of how to do some common things with Python,
so hopefully this will be useful for somebody out there.
"""
import re
import sys
from os.path import abspath, basename, dirname, join, splitext
from collections import namedtuple, Counter
from datetime import datetime
from random import shuffle

import yaml
from jinja2 import Environment, FileSystemLoader
from markdown import markdown
from xhtml2pdf import pisa


# Since we want to use smartypants on all of our Markdown to get smart quotes
# and other typographical goodies, we'll create a simple shortcut function.
def mkd(value):
    return markdown(value, extensions=['smartypants'])


# Let's keep our templates in a template directory alongside this file.
# Maybe someday add a command line switch to change this, or possibly
# look in the same directory as the source file for a templates dir first
rel = lambda *args: join(dirname(abspath(__file__)), *args)
template_dir = rel('templates')

# Load our Jinja template environment
templates = Environment(loader=FileSystemLoader(template_dir))

def render_to_pdf(data, template_name, output_name):
    "Render data in template_name to PDF at output_name"
    template = templates.get_template(template_name)
    html = template.render(data)
    pisa.CreatePDF(html, file(output_name, 'wb'))


# We could use a simple class for Question, but it's a good example
# of where namedtuple's are a nice option
Question = namedtuple('Question', 'id question notes answers correct format')


class Exam(object):
    """
    The Exam class maintains state for our exam (we parse the source file,
    populate the Exam's 'answers' with a list of Question instances) and
    contains writer methods for our exam and key PDFs.
    """
    exam_template = 'exam.html'
    key_template = 'key.html'

    def __init__(self, src):
        self.src = src
        self.now = datetime.now()

        # Containers for exam questions and metadata
        self.questions = []
        self.metadata = None
        self.counter = Counter()

        # Kick off the parsing of the source yaml file
        self.build()

    @staticmethod
    def get_indexes_for_answers(answers):
        """
        Correct answers start with '+'.
        Return a list of indexes in answers that contain correct answers
        """
        return [answers.index(x) for x in filter(lambda x: x.startswith('+'), answers)]

    @staticmethod
    def strip_keys(answers):
        "Strip the leading '+ ' from correct answers"
        return [re.sub(r'\+\ ?', '', x) for x in answers]

    def _process_metadata(self):
        "Get settings from preamble or set defaults"
        # shuffle question order each build
        self.metadata['shuffle-questions'] = self.metadata.get('shuffle-questions', False)
        # within each question, shuffle answer order each build
        self.metadata['shuffle-answers'] = self.metadata.get('shuffle-answers', True)
        # cancel build if a question with answers has no correct answer indicated
        self.metadata['require-correct'] = self.metadata.get('require-correct', True)

    def _build_question(self, doc):
        "Build a Question from a yaml doc"
        self.counter['questions'] += 1

        # quit for empty question
        if not doc.get('question'):
            print('Looks like question {0} is empty...'.format(
                self.counter['questions'] + 1))
            sys.exit()

        kwargs = {
            'id': self.counter['questions'],
            'question': mkd(doc.get('question', '')),
            'notes': mkd(doc.get('notes', '')),
            'answers': None,
            'correct': None,
            'format': 'open',
        }

        # if no answers are provided, it will stay format 'open' but if
        # there are answers then it is a multiple choice question...
        if doc.get('answers'):
            # answers need to be strings
            answers = map(unicode, doc['answers'])

            # (optionally) shuffle answers
            if self.metadata['shuffle-answers']:
                shuffle(answers)

            # identify correct answers
            correct = self.get_indexes_for_answers(answers)

            # now strip +'s in answers
            answers = self.strip_keys(answers)

            # (optionally) require at least one correct answer
            if not correct and self.metadata['require-correct']:
                print('Need a correct answer for "{0}"'.format(kwargs['question']))
                sys.exit()

            # update kwargs since this is a choice format
            kwargs.update(format='choice', answers=answers, correct=correct)

        self.questions.append(Question(**kwargs))

    def build(self):
        "Read yaml file and build out Exam object"
        raw = open(self.src, 'r').read()
        preamble = raw.split('---')[0]
        body = raw.replace(preamble, '')

        self.metadata = yaml.load(preamble)
        self._process_metadata()

        for doc in yaml.load_all(body):
            self._build_question(doc)

        # (optionally) shuffle question order
        if self.metadata['shuffle-questions']:
            shuffle(self.questions)

    def get_filename(self, description='exam'):
        base_dir = dirname(self.src)
        base_fname = splitext(basename(self.src))[0]
        today = self.now.strftime('%Y%m%d')  # '%Y%m%d-%H%M'
        return join(base_dir, u"{0}_{1}_{2}.pdf".format(base_fname, today, description))

    def get_context(self):
        return {'questions': self.questions, 'metadata': self.metadata}

    def write_exam(self):
        render_to_pdf(self.get_context(), self.exam_template, self.get_filename())

    def write_key(self):
        render_to_pdf(self.get_context(), self.key_template, self.get_filename('key'))


def build_test(src):
    exam = Exam(src)
    exam.write_exam()
    exam.write_key()


if __name__ == '__main__':
    pisa.showLogging()
    build_test(abspath(sys.argv[1]))
